"""Explicit operator CLI: process stored public notices, never approve or dispatch."""
import argparse
from decimal import Decimal
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from backend.exam_store import ExamStore
from backend.services.exams import ExamService
from backend.services.sarvam import SarvamService
from backend.storage import ServiceError


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--balance-credits',type=Decimal,help='Just-refreshed manual organisation credits balance; expires after 15 minutes, floor 500')
    parser.add_argument('--notice',help='Stored notice ID')
    parser.add_argument('--ocr',action='store_true',help='Recover stored PDF text using Sarvam Vision')
    parser.add_argument('--budget-inr',type=Decimal,help='Explicit total local reservation cap, at most 50 INR')
    parser.add_argument('--data-dir',type=Path)
    args=parser.parse_args()
    load_dotenv(Path(__file__).resolve().parents[1]/'.env')
    store=ExamStore((args.data_dir or Path(os.environ.get('NIYAMPULSE_DATA_DIR','var/production')))/'niyampulse.sqlite3')
    service=SarvamService(store)
    if args.budget_inr is not None:
        amount=args.budget_inr*100
        if amount!=amount.to_integral_value():parser.error('Budget supports whole paise only')
        service.set_budget(int(amount))
    if args.balance_credits is not None:
        amount=args.balance_credits*100
        if amount!=amount.to_integral_value():parser.error("Credits support two decimal places")
        service.record_credit_balance(int(amount))
    if args.notice:
        notice=ExamService(store).notice_detail(args.notice).notice
        try:
            if args.ocr:
                from backend.services.vision import VisionService
                result=VisionService(service).process(notice.notice_id,notice.revision)
            else:
                result=service.process(notice.notice_id,notice.revision)
            print(result.model_dump_json(indent=2))
        except ServiceError as error:
            print(error.code+': '+str(error));raise SystemExit(1) from None
    else:print(service.health().model_dump_json(indent=2))


if __name__=='__main__':main()
