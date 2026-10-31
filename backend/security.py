"""Bound API bodies before JSON/multipart parsing; preserve v1/v2 error shapes."""
import uuid
from starlette.responses import JSONResponse


class AccountRequestLimit:
    def __init__(self,app,limit=8192):self.app,self.limit=app,limit

    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or not scope['path'].startswith('/api/') or scope['method'] in {'GET','HEAD','OPTIONS'}:
            return await self.app(scope,receive,send)
        path=scope['path']
        limit=self.limit if path.startswith('/api/v2/auth/') else 256*1024
        if path.startswith('/api/v1/workspaces/') and path.endswith('/documents') and scope['method']=='POST':
            from backend.services.pdf_intake import MAX_PDF_BYTES
            limit=MAX_PDF_BYTES+64*1024
        async def too_large():
            request_id=scope.get('state',{}).get('request_id') or uuid.uuid4().hex
            message='Request body exceeds the endpoint size limit'
            if path.startswith('/api/v2/'):
                from backend.schemas import ApiError
                payload=ApiError(code='REQUEST_TOO_LARGE',message=message,request_id=request_id)
            else:
                from backend.legacy_schemas_v1 import ApiError
                payload=ApiError(error_code='REQUEST_TOO_LARGE',message=message,request_id=request_id)
            return await JSONResponse(payload.model_dump(mode='json'),status_code=413)(scope,receive,send)
        for key,value in scope.get('headers',[]):
            if key==b'content-length':
                try:
                    if int(value)>limit:return await too_large()
                except ValueError:pass
        messages=[];size=0
        while True:
            message=await receive()
            messages.append(message)
            if message['type']=='http.disconnect':return
            size+=len(message.get('body',b''))
            if size>limit:return await too_large()
            if not message.get('more_body',False):break
        async def bounded_receive():
            if messages:return messages.pop(0)
            return await receive()
        await self.app(scope,bounded_receive,send)
