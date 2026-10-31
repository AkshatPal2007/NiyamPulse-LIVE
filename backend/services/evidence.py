"""Immutable cached PDF pages; highlights only exact native-text matches."""
import hashlib
import pymupdf
from backend.storage import ServiceError
from backend import schemas as s

def source_bytes(store,notice_id):
    with store.connect() as con:
        row=con.execute('SELECT n.payload,s.content,s.content_type,s.sha256 FROM v2_notices n JOIN v2_snapshots s ON s.id=n.document_snapshot_id WHERE n.id=?',(notice_id,)).fetchone()
    if not row:raise ServiceError(404,'SOURCE_NOT_FOUND','No cached source exists')
    notice=s.DetectedNotice.model_validate_json(row['payload']);raw=bytes(row['content'])
    if hashlib.sha256(raw).hexdigest()!=row['sha256'] or row['sha256']!=notice.document_sha256:
        raise ServiceError(409,'SOURCE_INTEGRITY_FAILED','Cached source checksum does not match')
    return notice,raw,row['content_type']

def pdf_page(store,notice_id,page_number):
    notice,raw,kind=source_bytes(store,notice_id)
    if not raw.startswith(b'%PDF-'):raise ServiceError(415,'SOURCE_NOT_PDF','This source is a web listing; use its official link and literal excerpts')
    with pymupdf.open(stream=raw,filetype='pdf') as pdf:
        if not 1<=page_number<=len(pdf):raise ServiceError(404,'PAGE_NOT_FOUND','Page number is outside the source')
        page=pdf[page_number-1]
        literal=page.get_text()
        verified=0
        for anchor in notice.evidence:
            if anchor.page_number!=page_number or anchor.literal_quote not in literal:continue
            boxes=page.search_for(anchor.literal_quote)
            if boxes:
                page.add_highlight_annot(boxes);verified+=1
        scale=min(1.7,1400/max(page.rect.width,page.rect.height))
        return page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),alpha=False).tobytes('png'),verified
