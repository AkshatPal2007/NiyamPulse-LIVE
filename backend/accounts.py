"""Trusted local administrator setup. Passwords are chosen through emailed links."""
import argparse
from pathlib import Path
import os
from dotenv import load_dotenv

from backend import schemas as s
from backend.exam_store import ExamStore
from backend.services.auth import AuthService,normalized_email
from backend.storage import ServiceError,utc_text


def main():
    load_dotenv(Path(__file__).resolve().parents[1]/'.env')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['invite-admin','promote-admin','status'])
    parser.add_argument('--email',help='Real account owner; omit to enter privately at the prompt')
    args=parser.parse_args()
    store=ExamStore(Path(os.environ.get('NIYAMPULSE_DATA_DIR','var/production'))/'niyampulse.sqlite3')
    auth=AuthService(store)
    try:
        if args.action=='status':
            with store.connect() as con:
                print('Verified administrators:',con.execute("SELECT count(*) FROM v2_users u JOIN v2_credentials c ON c.user_id=u.id WHERE u.role='ADMIN' AND c.email_verified_at IS NOT NULL").fetchone()[0])
            print('Account email configured:',auth.config().email_delivery_configured)
            return
        email=normalized_email(args.email or input('Administrator email address: ').strip())
        if args.action=='invite-admin':
            if input('Confirm the account holder is 18 or older. Type YES: ').strip()!='YES':raise SystemExit('No invitation sent.')
            message=auth.request_registration(s.RegisterRequest(email=email,display_name='Administrator',adult_confirmed=True),'trusted-local-console',role='ADMIN')
            if not auth.dispatch(message):raise ServiceError(503,'EMAIL_DELIVERY_FAILED','SMTP did not accept the administrator invitation; inspect local mail settings')
            print('Invitation accepted by SMTP. Open the email on this device and choose your private password.')
        else:
            if input('Type PROMOTE to grant administrator access to this verified account: ').strip()!='PROMOTE':raise SystemExit('No role changed.')
            with store.connect(write=True) as con:
                row=con.execute('SELECT user_id FROM v2_credentials WHERE email=? AND email_verified_at IS NOT NULL',(email,)).fetchone()
                if row is None:raise ServiceError(404,'VERIFIED_ACCOUNT_REQUIRED','Create and verify the account first')
                con.execute("UPDATE v2_users SET role='ADMIN' WHERE id=? AND synthetic=0",(row[0],))
                con.execute('DELETE FROM v2_auth_sessions WHERE user_id=?',(row[0],))
                con.execute('INSERT INTO v2_auth_events(created_at,event) VALUES (?,?)',(utc_text(auth.clock()),'ADMIN_PROMOTED:'+row[0]))
            print('Administrator role granted. Sign in again.')
    except ServiceError as error:raise SystemExit(error.code+': '+str(error)) from None


if __name__=='__main__':main()
