"""Owned subscriptions, reviewed informational publication and in-app delivery."""
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import json
import secrets
import uuid

from pydantic import ValidationError

from backend import schemas as s
from backend.storage import ServiceError,utc_text
from backend.services.rule_engine import content_fingerprint


def identifier(prefix): return prefix+"-"+uuid.uuid4().hex


class ExamService:
    def __init__(self,store,*,demo=False,clock=None):
        self.store,self.demo=store,demo
        self.clock=clock or (lambda:datetime.now(timezone.utc))
        if demo: store.seed_demo_users()

    def login_demo(self,persona):
        if not self.demo: raise ServiceError(403,"DEMO_DISABLED","Local demo sessions are disabled")
        user_id="demo-"+persona
        token=secrets.token_urlsafe(32)
        expires=self.clock()+timedelta(hours=8)
        with self.store.connect(write=True) as con:
            user=con.execute("SELECT * FROM v2_users WHERE id=?",(user_id,)).fetchone()
            if user is None: raise ServiceError(404,"ACCOUNT_REMOVED","This local demo account was deleted")
            con.execute("INSERT INTO v2_sessions VALUES (?,?,?)",(hashlib.sha256(token.encode()).hexdigest(),user_id,utc_text(expires)))
            profile=s.UserProfileV2.model_validate_json(user["profile"])
            return s.SessionResponse(access_token=token,user_id=user_id,display_name=profile.display_name or user_id,role=user["role"],expires_at=expires)

    def identity(self,authorization):
        if not authorization or not authorization.startswith("Bearer "):
            raise ServiceError(401,"SESSION_REQUIRED","Select a local demo persona to continue")
        digest=hashlib.sha256(authorization[7:].encode()).hexdigest()
        with self.store.connect() as con:
            row=con.execute("SELECT u.* FROM v2_sessions t JOIN v2_users u ON u.id=t.user_id WHERE t.token_hash=? AND t.expires_at>?",(digest,utc_text(self.clock()))).fetchone()
            if row is None: raise ServiceError(401,"SESSION_EXPIRED","Session is missing or expired")
            return dict(row)

    def subscriptions(self,user_id):
        with self.store.connect() as con:
            return [s.ExamSubscription.model_validate_json(r[0]) for r in con.execute("SELECT payload FROM v2_subscriptions WHERE user_id=? ORDER BY rowid",(user_id,))]

    def subscribe(self,user_id,body):
        with self.store.connect(write=True) as con:
            row=con.execute("SELECT c.payload,e.payload FROM v2_cycles c JOIN v2_exams e ON e.id=c.exam_id WHERE c.id=?",(body.cycle_id,)).fetchone()
            if row is None or not s.ExamCycle.model_validate_json(row[0]).is_active or not s.ExamCatalogEntry.model_validate_json(row[1]).active:
                raise ServiceError(404,"CYCLE_UNAVAILABLE","Exam cycle is not available for subscription")
            old=con.execute("SELECT payload FROM v2_subscriptions WHERE user_id=? AND cycle_id=?",(user_id,body.cycle_id)).fetchone()
            if old:
                existing=s.ExamSubscription.model_validate_json(old[0])
                if existing.topics != body.topics or existing.application_status != body.application_status:
                    raise ServiceError(409,"SUBSCRIPTION_EXISTS","Edit the existing subscription to change its preferences")
                return existing
            item=s.ExamSubscription(subscription_id=identifier("sub"),user_id=user_id,cycle_id=body.cycle_id,topics=body.topics,application_status=body.application_status,subscribed_at=self.clock())
            con.execute("INSERT INTO v2_subscriptions VALUES (?,?,?,?)",(item.subscription_id,user_id,item.cycle_id,item.model_dump_json()))
            if not self.demo:
                recent=con.execute('SELECT u.payload AS update_payload,n.payload AS notice_payload FROM v2_updates u JOIN v2_notices n ON n.id=u.notice_id WHERE u.cycle_id=? ORDER BY u.rowid DESC LIMIT 20',(item.cycle_id,)).fetchall()
                for saved in recent:
                    update=s.NoticeUpdate.model_validate_json(saved['update_payload'])
                    notice=s.DetectedNotice.model_validate_json(saved['notice_payload'])
                    if update.rule_changes or update.published_at<self.clock()-timedelta(days=30):continue
                    if notice.source_kind!=s.SourceKind.OFFICIAL_WEB_LISTING or notice.review_status!=s.ReviewStatus.APPROVED:continue
                    self._fanout(con,notice,update,self.clock(),only_subscription_id=item.subscription_id)
            return item

    def change_subscription(self,user_id,subscription_id,body=None):
        with self.store.connect(write=True) as con:
            row=con.execute("SELECT payload FROM v2_subscriptions WHERE id=? AND user_id=?",(subscription_id,user_id)).fetchone()
            if row is None: raise ServiceError(404,"SUBSCRIPTION_NOT_FOUND","Subscription not found")
            if body is None:
                con.execute("DELETE FROM v2_subscriptions WHERE id=?",(subscription_id,)); return
            item=s.ExamSubscription.model_validate(json.loads(row[0]) | body.model_dump(mode="json",exclude_none=True))
            con.execute("UPDATE v2_subscriptions SET payload=? WHERE id=?",(item.model_dump_json(),subscription_id))
            return item

    def profile(self,user_id,patch=None,clear=False):
        with self.store.connect(write=patch is not None or clear) as con:
            row=con.execute("SELECT profile FROM v2_users WHERE id=?",(user_id,)).fetchone()
            if row is None: raise ServiceError(404,"PROFILE_NOT_FOUND","Profile not found")
            data=json.loads(row[0])
            if patch is not None: data |= patch.model_dump(mode="json",exclude_unset=True)
            if clear or (patch is not None and patch.personalization_opt_in is False):
                data |= dict(personalization_opt_in=False,date_of_birth=None,marks_percent=None,annual_household_income_inr=None,available_document_codes=[],document_inventory_complete=False)
            if patch is not None or clear: data["updated_at"]=utc_text(self.clock())
            try: item=s.UserProfileV2.model_validate(data)
            except ValidationError as error: raise ServiceError(422,"PROFILE_OPT_IN_REQUIRED","Valid profile fields require explicit personalization opt-in") from error
            if patch is not None or clear: con.execute("UPDATE v2_users SET profile=? WHERE id=?",(item.model_dump_json(),user_id))
            return item

    def delete_account(self,user_id):
        with self.store.connect(write=True) as con:
            con.execute("INSERT OR IGNORE INTO metadata VALUES (?,?)",("v2_deleted:"+user_id,utc_text(self.clock())))
            con.execute("DELETE FROM v2_users WHERE id=? AND role='USER'",(user_id,))

    def _cursor(self,con,user_id,position=None):
        secret=bytes.fromhex(con.execute("SELECT value FROM metadata WHERE key='cursor_secret'").fetchone()[0])
        def sign(text): return hmac.new(secret,text.encode(),hashlib.sha256).hexdigest()
        if isinstance(position,str):
            try:
                body,signature=position.split(".")
                if not hmac.compare_digest(sign(body),signature): raise ValueError()
                owner,index=json.loads(base64.urlsafe_b64decode(body+"="*(-len(body)%4)))
                if owner!=user_id or type(index) is not int or index<0: raise ValueError()
                return index
            except (ValueError,TypeError): raise ServiceError(400,"INVALID_CURSOR","Invalid inbox cursor") from None
        body=base64.urlsafe_b64encode(json.dumps([user_id,position],separators=(",",":")).encode()).decode().rstrip("=")
        return body+"."+sign(body)

    def notifications(self,user_id,cursor=None,limit=30,unread_only=False):
        with self.store.connect() as con:
            index=self._cursor(con,user_id,cursor) if cursor else 9223372036854775807
            rows=con.execute("SELECT rowid,payload FROM v2_notifications WHERE user_id=? AND rowid<? ORDER BY rowid DESC",(user_id,index)).fetchall()
            items=[(r[0],s.InAppNotification.model_validate_json(r[1])) for r in rows]
            if unread_only: items=[i for i in items if i[1].read_at is None]
            selected=items[:limit]
            next_cursor=self._cursor(con,user_id,selected[-1][0]) if len(items)>limit else None
            unread=con.execute("SELECT count(*) FROM v2_notifications WHERE user_id=? AND json_extract(payload,'$.read_at') IS NULL",(user_id,)).fetchone()[0]
            return s.NotificationsResponse(notifications=[i[1] for i in selected],next_cursor=next_cursor,unread_count=unread)

    def notification(self,user_id,notification_id,mark_read=False):
        with self.store.connect(write=mark_read) as con:
            row=con.execute("SELECT payload,match_id,update_id FROM v2_notifications WHERE id=? AND user_id=?",(notification_id,user_id)).fetchone()
            if row is None: raise ServiceError(404,"NOTIFICATION_NOT_FOUND","Notification not found")
            item=s.InAppNotification.model_validate_json(row[0])
            if mark_read:
                if item.read_at is None:
                    item.read_at=self.clock();item.delivery=s.DeliveryState.READ
                    con.execute("UPDATE v2_notifications SET payload=? WHERE id=?",(item.model_dump_json(),notification_id))
                return item
            match=s.RecipientMatch.model_validate_json(con.execute("SELECT payload FROM v2_matches WHERE id=?",(row[1],)).fetchone()[0])
            update=s.NoticeUpdate.model_validate_json(con.execute("SELECT payload FROM v2_updates WHERE id=?",(row[2],)).fetchone()[0])
            notice=s.DetectedNotice.model_validate_json(con.execute("SELECT payload FROM v2_notices WHERE id=?",(update.notice_id,)).fetchone()[0])
            return s.InboxItem(notification=item,match=match,update=update,notice=notice)

    def notices(self,review_status=None,cycle_id=None):
        with self.store.connect() as con:
            items=[s.DetectedNotice.model_validate_json(r[0]) for r in con.execute("SELECT payload FROM v2_notices ORDER BY rowid DESC")]
            return [i for i in items if (not review_status or i.review_status==review_status) and (not cycle_id or i.cycle_id==cycle_id)]

    def notice_detail(self,notice_id):
        with self.store.connect() as con:
            row=con.execute("SELECT * FROM v2_notices WHERE id=?",(notice_id,)).fetchone()
            if row is None: raise ServiceError(404,"NOTICE_NOT_FOUND","Notice not found")
            analysis=con.execute("SELECT payload FROM v2_notice_analysis WHERE notice_id=?",(notice_id,)).fetchone()
            return s.NoticeDetail(analysis=s.NoticeAnalysis.model_validate_json(analysis[0]) if analysis and json.loads(analysis[0])["extraction_id"]==row["extraction_id"] else None,notice=s.DetectedNotice.model_validate_json(row["payload"]),extracted_pages=json.loads(row["pages"]),source_listing_url=row["listing_url"],observed_link_title=row["observed_link_title"],extraction_version=row["extraction_version"])

    def review(self,notice_id,request,reviewer_id):
        if request.notice_id!=notice_id or request.reviewer_id!=reviewer_id:
            raise ServiceError(403,"REVIEW_IDENTITY_MISMATCH","Review must name the authenticated platform operator and notice")
        fingerprint=content_fingerprint(request.model_dump(mode="json"))
        with self.store.connect(write=True) as con:
            old=con.execute("SELECT request_hash,response FROM v2_reviews WHERE notice_id=? AND expected_revision=?",(notice_id,request.expected_revision)).fetchone()
            if old:
                if old[0]!=fingerprint: raise ServiceError(409,"IDEMPOTENCY_CONFLICT","Revision was already reviewed with a different request")
                return s.DetectedNotice.model_validate_json(old[1])
            row=con.execute("SELECT * FROM v2_notices WHERE id=?",(notice_id,)).fetchone()
            if row is None: raise ServiceError(404,"NOTICE_NOT_FOUND","Notice not found")
            notice=s.DetectedNotice.model_validate_json(row["payload"])
            if notice.revision!=request.expected_revision or notice.review_status not in {s.ReviewStatus.NEEDS_REVIEW,s.ReviewStatus.QUARANTINED}:
                raise ServiceError(409,"STALE_NOTICE_REVISION","Refresh the review queue before acting")
            now=self.clock()
            if request.action=="APPROVE":
                self._verify_publication(con,row,notice)
                from backend.services.sarvam import verified_analysis
                analysis=verified_analysis(con,row,notice)
                notice.review_status=s.ReviewStatus.APPROVED
                # --- Rule bridge: validate and apply rule changes if flagged ---
                bridge_result=None
                notice_changes=[]
                rule_set_sha256=None
                if notice.requires_rule_validation:
                    if not (analysis and getattr(analysis, "notice_changes", None)):
                        raise ServiceError(409, "RULE_VALIDATION_REQUIRED", "Supported rule amendments need the deterministic validation bridge; informational publication cannot bypass it")
                    bridge_result,notice_changes,rule_set_sha256=self._run_rule_bridge(con,notice,analysis,now)
                    if not bridge_result:
                        raise ServiceError(409, "RULE_VALIDATION_REQUIRED", "Deterministic rule bridge produced no valid rule changes")
                update=s.NoticeUpdate(
                    update_id=identifier("update"),cycle_id=notice.cycle_id,
                    notice_id=notice_id,notice_type=notice.notice_type,published_at=now,
                    summary_en=analysis.summary_en if analysis else notice.evidence[0].literal_quote[:1600],
                    summary_hi=analysis.summary_hi if analysis else None,
                    evidence=notice.evidence,approved_by=reviewer_id,approved_at=now,
                    evaluation_version="cycle-topic-v1" if not bridge_result else "rule-bridge-v1",
                    rule_changes=notice_changes,
                    rule_set_sha256=rule_set_sha256,
                )
                con.execute("INSERT INTO v2_updates VALUES (?,?,?,?)",(update.update_id,notice_id,notice.cycle_id,update.model_dump_json()))
                if bridge_result is not None:
                    self.store.persist_rule_changes(con,cycle_id=notice.cycle_id,update_id=update.update_id,bridge_result=bridge_result,now_text=utc_text(now),expected_revision=analysis.rule_set_revision)
                self._fanout(con,notice,update,now,bridge_result=bridge_result)
            else: notice.review_status=s.ReviewStatus.QUARANTINED if request.action=="QUARANTINE" else s.ReviewStatus.REJECTED
            notice.revision+=1
            con.execute("UPDATE v2_notices SET payload=? WHERE id=?",(notice.model_dump_json(),notice_id))
            con.execute("UPDATE v2_processing_jobs SET status='COMPLETE',lease_until=NULL,last_error=NULL,updated_at=? WHERE notice_id=?",(utc_text(now),notice_id))
            con.execute('DELETE FROM v2_processing_leases WHERE notice_id=?',(notice_id,))
            con.execute("INSERT INTO v2_reviews VALUES (?,?,?,?,?,?)",(notice_id,request.expected_revision,fingerprint,notice.model_dump_json(),reviewer_id,utc_text(now)))
            return notice

    def _run_rule_bridge(self,con,notice,analysis,now):
        """Run the deterministic rule bridge and return (BridgeResult, notice_changes, rule_set_sha256).

        Raises ServiceError if the bridge rejects the changes.
        """
        from backend.services.rule_bridge import apply_rule_bridge, profile_from_v2
        from backend.services.rule_engine import EngineError as Err
        from backend.services.rule_bridge import verify_change_proposals
        notice_changes=analysis.notice_changes
        if analysis.rule_set_revision!=self.store.rule_revision(con,notice.cycle_id):
            raise ServiceError(409,'STALE_RULE_REVISION','Reanalyze against the current rule-set revision')
        before_rules,before_hashes=self.store.rule_set_for_cycle(con,notice.cycle_id)
        try: change_proofs,rule_proofs=verify_change_proposals(analysis,notice,before_rules)
        except Err as error:raise ServiceError(409,error.code,str(error)) from error
        # Gather opted-in subscribers for this cycle
        subs=con.execute("SELECT payload FROM v2_subscriptions WHERE cycle_id=?",(notice.cycle_id,)).fetchall()
        subscriber_inputs=[]
        for sub_row in subs:
            sub=s.ExamSubscription.model_validate_json(sub_row[0])
            if not sub.notifications_enabled or sub.application_status==s.ApplicationStatus.NO_LONGER_INTERESTED: continue
            profile_row=con.execute("SELECT profile FROM v2_users WHERE id=?",(sub.user_id,)).fetchone()
            if profile_row is None: continue
            v2prof=s.UserProfileV2.model_validate_json(profile_row[0])
            legacy_profile=profile_from_v2(v2prof)
            subscriber_inputs.append((sub.user_id,sub.subscription_id,legacy_profile))
        try:
            result=apply_rule_bridge(
                notice_changes=notice_changes,
                before_rules=before_rules,
                before_verified_hashes=before_hashes,
                scheme_id=notice.cycle_id,
                subscribers=subscriber_inputs,
                as_of_date=now.astimezone(timezone(timedelta(hours=5,minutes=30))).date(),
                verified_change_hashes=change_proofs,
                verified_proposed_rule_hashes=rule_proofs,
                cycle_id=notice.cycle_id,
            )
        except Err as e:
            raise ServiceError(409,"RULE_BRIDGE_REJECTED",str(e)) from e
        return result,notice_changes,result.after_rule_set_sha256

    def _verify_publication(self,con,row,notice,*,evidence_only=False):
        if not evidence_only:
            analysis=con.execute("SELECT payload FROM v2_notice_analysis WHERE notice_id=?",(notice.notice_id,)).fetchone()
            if analysis and json.loads(analysis[0])["extraction_id"]==row["extraction_id"] and json.loads(analysis[0])["status"]=="GUARD_REJECTED":
                raise ServiceError(409,"ANALYSIS_GUARD_BLOCKED","Candidate evidence failed validation; recover/reprocess the source or quarantine this notice")
        if not evidence_only:
            from backend.services.sarvam import requires_rule_review
            stored_analysis=con.execute('SELECT payload FROM v2_notice_analysis WHERE notice_id=?',(notice.notice_id,)).fetchone()
            data=json.loads(stored_analysis[0]) if stored_analysis else {}
            candidate=data.get('candidate') or {}
            derived=requires_rule_review(notice.title+'\n'+'\n'.join(json.loads(row['pages']))) or candidate.get('requires_rule_validation',False) or any(f.get('kind') in {'RULE_CANDIDATE','UNSUPPORTED_REQUIREMENT'} for f in candidate.get('facts',[])) or bool(data.get('notice_changes'))
            if derived and not notice.requires_rule_validation:
                raise ServiceError(409,'RULE_VALIDATION_REQUIRED','Source contains rule requirements: reprocess before publication')
        if notice.requires_rule_validation and not evidence_only:
            analysis_row = con.execute("SELECT payload FROM v2_notice_analysis WHERE notice_id=?", (notice.notice_id,)).fetchone()
            if not analysis_row:
                raise ServiceError(409, "RULE_VALIDATION_REQUIRED", "Supported rule amendments need the deterministic validation bridge; informational publication cannot bypass it")
            analysis_data = json.loads(analysis_row[0])
            if analysis_data.get("status") != "VALIDATED" or not analysis_data.get("notice_changes"):
                raise ServiceError(409, "RULE_VALIDATION_REQUIRED", "Supported rule amendments need the deterministic validation bridge; informational publication cannot bypass it")
        if (not notice.evidence and not (evidence_only and notice.processing_mode=="NEEDS_EXTRACTION")) or notice.trust==s.DocumentTrust.MISMATCH:
            raise ServiceError(409,"SOURCE_GATE_BLOCKED","Source mismatch or missing literal evidence")
        if notice.source_kind!=s.SourceKind.LOCAL_DEMO_FIXTURE and notice.trust!=s.DocumentTrust.MATCHED_CONFIGURED_SOURCE:
            raise ServiceError(409,"SOURCE_GATE_BLOCKED","A configured and observed source is required")
        snapshot=con.execute("SELECT * FROM v2_snapshots WHERE id=?",(row["document_snapshot_id"],)).fetchone()
        if hashlib.sha256(bytes(snapshot["content"])).hexdigest()!=notice.document_sha256:
            raise ServiceError(409,"SOURCE_INTEGRITY_FAILED","Immutable source checksum failed")
        pages=json.loads(row["pages"])
        extraction=con.execute("SELECT * FROM v2_extractions WHERE id=?",(row["extraction_id"],)).fetchone()
        expected_id="extract-"+hashlib.sha256(f"{notice.document_sha256}:{row['extraction_version']}".encode()).hexdigest()
        if (extraction is None or row["extraction_id"]!=expected_id or extraction["version"]!=row["extraction_version"]
            or hashlib.sha256(extraction["pages"].encode()).hexdigest()!=extraction["pages_sha"] or extraction["pages"]!=row["pages"]):
            raise ServiceError(409,"EXTRACTION_INTEGRITY_FAILED","Immutable extracted text does not match the review record")
        for anchor in notice.evidence:
            if (anchor.document_sha256!=notice.document_sha256 or anchor.document_id!=notice.notice_id
                or anchor.extraction_id!=row["extraction_id"] or not 1<=anchor.page_number<=len(pages)):
                raise ServiceError(409,"EVIDENCE_MISMATCH","Evidence identity does not match the source extraction")
            page=pages[anchor.page_number-1]
            if anchor.start_char is None or page[anchor.start_char:anchor.end_char]!=anchor.literal_quote:
                raise ServiceError(409,"EVIDENCE_MISMATCH","Literal evidence does not match frozen page text")
        if notice.source_kind==s.SourceKind.OFFICIAL_WEB_LISTING:
            from backend.services.source_monitor import validate_public_url,parse_listing
            source=s.OfficialSource.model_validate_json(con.execute("SELECT payload FROM v2_sources WHERE id=?",(notice.source_id,)).fetchone()[0])
            validate_public_url(str(notice.source_url),source.allowed_hosts,resolve=False)
            listing=con.execute("SELECT * FROM v2_snapshots WHERE id=?",(row["listing_snapshot_id"],)).fetchone()
            if listing is None or hashlib.sha256(bytes(listing["content"])).hexdigest()!=listing["sha256"]:
                raise ServiceError(409,"LISTING_INTEGRITY_FAILED","Observed listing capture is unavailable")
            links=parse_listing(source,bytes(listing["content"]))
            if snapshot['url']!=row['canonical_url']:raise ServiceError(409,'SOURCE_LINEAGE_FAILED','Captured document URL differs from observed link')
            direct=any(link.url==row['canonical_url'] and link.cycle_id==notice.cycle_id and link.title==row['observed_link_title'] for link in links)
            if not direct:
                from backend.services.source_monitor import parse_attachments,ListingLink
                lineage=con.execute('SELECT * FROM v2_attachment_lineage WHERE notice_id=?',(notice.notice_id,)).fetchone()
                if lineage is None:raise ServiceError(409,'SOURCE_LINEAGE_FAILED','No observed attachment ancestry')
                parent=ListingLink(lineage['parent_title'],lineage['parent_url'],notice.cycle_id)
                parent_capture=con.execute('SELECT * FROM v2_snapshots WHERE id=?',(lineage['parent_snapshot_id'],)).fetchone()
                if (not any(link==parent for link in links) or parent_capture is None or parent_capture['url']!=parent.url or parent_capture['source_id']!=notice.source_id or hashlib.sha256(bytes(parent_capture['content'])).hexdigest()!=parent_capture['sha256']):
                    raise ServiceError(409,'SOURCE_LINEAGE_FAILED','Attachment parent does not match immutable configured listing')
                children=parse_attachments(source,parent,bytes(parent_capture['content']))
                if not any(child.url==row['canonical_url'] and child.title==row['observed_link_title'] and child.cycle_id==notice.cycle_id for child in children):
                    raise ServiceError(409,'SOURCE_LINEAGE_FAILED','Attachment was not observed in captured exam detail page')

    def _fanout(self,con,notice,update,now,*,bridge_result=None,only_subscription_id=None):
        # Build a lookup of user_id -> PersonalImpactRow for bridge publications
        impact_map={}
        if bridge_result is not None:
            for imp in bridge_result.impacts:
                impact_map[imp.user_id]=imp
        for row in con.execute("SELECT payload FROM v2_subscriptions WHERE cycle_id=? AND (? IS NULL OR id=?)",(notice.cycle_id,only_subscription_id,only_subscription_id)).fetchall():
            sub=s.ExamSubscription.model_validate_json(row[0])
            if con.execute('SELECT 1 FROM v2_notifications WHERE update_id=? AND user_id=?',(update.update_id,sub.user_id)).fetchone():continue
            if not sub.notifications_enabled or sub.application_status==s.ApplicationStatus.NO_LONGER_INTERESTED: continue
            if s.Topic.ALL not in sub.topics and not set(sub.topics).intersection(notice.topics): continue
            imp=impact_map.get(sub.user_id)
            if imp is not None:
                relevance=imp.relevance
                reason_codes=["SUBSCRIBED_CYCLE","REVIEWED_RULE_CHANGE"]
                if imp.changed:
                    reason_codes.append("DECISION_STATUS_CHANGED")
                match=s.RecipientMatch(
                    match_id=identifier("match"),update_id=update.update_id,
                    user_id=sub.user_id,subscription_id=sub.subscription_id,
                    relevance=relevance,reason_codes=reason_codes,
                    before=imp.before,after=imp.after,
                )
            else:
                match=s.RecipientMatch(
                    match_id=identifier("match"),update_id=update.update_id,
                    user_id=sub.user_id,subscription_id=sub.subscription_id,
                    relevance=s.RecipientRelevance.GENERAL_UPDATE,
                    reason_codes=["SUBSCRIBED_CYCLE","SUBSCRIBED_TOPIC","REVIEWED_INFORMATIONAL_NOTICE"],
                )
            con.execute("INSERT INTO v2_matches VALUES (?,?,?,?,?)",(match.match_id,update.update_id,sub.user_id,sub.subscription_id,match.model_dump_json()))
            headline=("SYNTHETIC DEMO · " if notice.source_kind==s.SourceKind.LOCAL_DEMO_FIXTURE else "")+notice.title
            profile=s.UserProfileV2.model_validate_json(con.execute("SELECT profile FROM v2_users WHERE id=?",(sub.user_id,)).fetchone()[0])
            use_hindi=profile.preferred_language==s.Language.HI and bool(update.summary_hi)
            item=s.InAppNotification(
                notification_id=identifier("notification"),user_id=sub.user_id,
                match_id=match.match_id,update_id=update.update_id,cycle_id=notice.cycle_id,
                delivery=s.DeliveryState.DELIVERED,headline=headline[:500],
                body=(update.summary_hi if use_hindi else update.summary_en)[:1600],
                language=s.Language.HI if use_hindi else s.Language.EN,
                created_at=now,delivered_at=now,
                official_source_url=notice.source_url,evidence=notice.evidence,
            )
            con.execute("INSERT INTO v2_notifications VALUES (?,?,?,?,?)",(item.notification_id,update.update_id,sub.user_id,match.match_id,item.model_dump_json()))

    def recipients(self,update_id):
        with self.store.connect() as con:
            if not con.execute("SELECT 1 FROM v2_updates WHERE id=?",(update_id,)).fetchone(): raise ServiceError(404,"UPDATE_NOT_FOUND","Update not found")
            return [s.RecipientMatch.model_validate_json(r[0]) for r in con.execute("SELECT payload FROM v2_matches WHERE update_id=?",(update_id,))]

    def public_updates(self,cycle_id=None,limit=30):
        with self.store.connect() as con:
            rows=con.execute("SELECT u.payload AS update_payload,n.payload AS notice_payload,s.payload AS source_payload FROM v2_updates u JOIN v2_notices n ON n.id=u.notice_id JOIN v2_sources s ON s.id=n.source_id WHERE (? IS NULL OR u.cycle_id=?) ORDER BY u.rowid DESC",(cycle_id,cycle_id)).fetchall()
            updates=[]
            for row in rows:
                notice=s.DetectedNotice.model_validate_json(row['notice_payload'])
                if notice.source_kind!=s.SourceKind.OFFICIAL_WEB_LISTING or notice.review_status!=s.ReviewStatus.APPROVED:continue
                update=s.NoticeUpdate.model_validate_json(row['update_payload'])
                source=s.OfficialSource.model_validate_json(row['source_payload'])
                updates.append(s.PublicUpdate(update_id=update.update_id,notice_id=notice.notice_id,cycle_id=notice.cycle_id,title=notice.title,notice_type=notice.notice_type,topics=notice.topics,publisher=source.organization,source_url=notice.source_url,published_at=update.published_at,first_seen_at=notice.first_seen_at,source_published_on=notice.published_on,summary_en=update.summary_en,summary_hi=update.summary_hi,evidence=update.evidence))
            return s.PublicUpdatesResponse(updates=updates[:limit],total=len(updates))

    def public_sources(self):
        with self.store.connect() as con:
            heartbeat=con.execute("SELECT value FROM metadata WHERE key='v2_monitor_heartbeat'").fetchone()
            running=bool(heartbeat and timedelta(0)<=self.clock()-datetime.fromisoformat(heartbeat[0].replace('Z','+00:00'))<timedelta(seconds=90))
            result=[]
            for source in self.store.sources(con):
                health=s.SourceHealth.model_validate_json(con.execute('SELECT health FROM v2_sources WHERE id=?',(source.source_id,)).fetchone()[0])
                status='CATALOG_ONLY' if not source.enabled else 'UNAVAILABLE' if health.status=='ERROR' else 'LIVE_MONITORED' if running and health.status=='LIVE_OK' else 'SOURCE_CONFIGURED'
                result.append(s.PublicSource(source_id=source.source_id,publisher=source.organization,listing_url=source.listing_url,enabled=source.enabled,last_success_at=health.last_success_at,status=status))
            return result

    def dashboard(self):
        with self.store.connect() as con:
            count=lambda sql,args=():con.execute(sql,args).fetchone()[0]
            notices=[s.DetectedNotice.model_validate_json(r[0]) for r in con.execute("SELECT payload FROM v2_notices")]
            subscriptions=[s.ExamSubscription.model_validate_json(r[0]) for r in con.execute("SELECT payload FROM v2_subscriptions")]
            notifications=[s.InAppNotification.model_validate_json(r[0]) for r in con.execute("SELECT payload FROM v2_notifications")]
            sources=self.store.sources(con)
            checks=[s.SourceHealth.model_validate_json(r[0]) for r in con.execute("SELECT health FROM v2_sources ORDER BY rowid")]
            heartbeat=con.execute("SELECT value FROM metadata WHERE key='v2_monitor_heartbeat'").fetchone()
            running=bool(heartbeat and heartbeat[0] and self.clock()-datetime.fromisoformat(heartbeat[0].replace('Z','+00:00'))<timedelta(seconds=90))
            totals=s.AdminDashboardTotals(monitored_sources=sum(item.enabled for item in sources) if running else 0,
                active_exam_cycles=sum(s.ExamCycle.model_validate_json(r[0]).is_active for r in con.execute("SELECT payload FROM v2_cycles")),
                registered_users=(count("SELECT count(*) FROM v2_users WHERE role='USER'") if self.demo else count("SELECT count(*) FROM v2_users u JOIN v2_credentials c ON c.user_id=u.id WHERE u.role='USER' AND u.synthetic=0 AND c.email_verified_at IS NOT NULL")),active_subscriptions=sum(i.notifications_enabled and i.application_status!=s.ApplicationStatus.NO_LONGER_INTERESTED for i in subscriptions),
                notices_detected=len(notices),notices_pending_review=sum(i.review_status in {s.ReviewStatus.DETECTED,s.ReviewStatus.PROCESSING,s.ReviewStatus.NEEDS_REVIEW} for i in notices),
                approved_updates=count("SELECT count(*) FROM v2_updates"),matched_recipients=count("SELECT count(*) FROM v2_matches"),
                notifications_delivered=sum(i.delivery in {s.DeliveryState.DELIVERED,s.DeliveryState.READ} for i in notifications),notifications_failed=sum(i.delivery==s.DeliveryState.FAILED for i in notifications),notifications_read=sum(i.delivery==s.DeliveryState.READ for i in notifications))
            by_cycle=[s.CycleTotals(cycle_id=r[0],subscriptions=count("SELECT count(*) FROM v2_subscriptions WHERE cycle_id=?",(r[0],)),updates=count("SELECT count(*) FROM v2_updates WHERE cycle_id=?",(r[0],)),notifications=count("SELECT count(*) FROM v2_notifications n JOIN v2_updates u ON u.id=n.update_id WHERE u.cycle_id=?",(r[0],))) for r in con.execute("SELECT id FROM v2_cycles")]
            return s.AdminDashboardResponse(generated_at=self.clock(),totals=totals,recent_updates=[s.NoticeUpdate.model_validate_json(r[0]) for r in con.execute("SELECT payload FROM v2_updates ORDER BY rowid DESC LIMIT 10")],
                                            source_health={c.source_id:c.status for c in checks},source_checks=checks,by_cycle=by_cycle,synthetic_demo=self.demo,monitor_running=running)
