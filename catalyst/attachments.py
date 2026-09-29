import base64, hashlib, mimetypes
from pathlib import Path
from uuid import uuid4

MAX_FILE_BYTES=12*1024*1024
IMAGE_TYPES={'image/png','image/jpeg','image/webp','image/gif'}
TEXT_TYPES={'text/plain','text/markdown','application/json','application/xml','text/csv','text/html','text/css','text/javascript'}

ALLOWED_BINARY={'application/pdf','application/zip','application/octet-stream'}

class AttachmentStore:
    def __init__(self, root):
        self.root=Path(root)/'attachments'; self.root.mkdir(parents=True,exist_ok=True)
    def save(self, filename, data, content_type=None):
        if len(data)>MAX_FILE_BYTES: raise ValueError(f'Attachment exceeds {MAX_FILE_BYTES//(1024*1024)} MB limit')
        ext=Path(filename).suffix[:12]
        safe=f'{uuid4().hex}{ext}'
        path=self.root/safe; path.write_bytes(data)
        digest=hashlib.sha256(data).hexdigest(); ctype=content_type or mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        return {'id':safe,'name':Path(filename).name,'path':str(path),'size':len(data),'sha256':digest,'content_type':ctype,'image':ctype in IMAGE_TYPES,'text':ctype in TEXT_TYPES,'binary':ctype not in IMAGE_TYPES and ctype not in TEXT_TYPES}
    def delete(self, attachment_id):
        p=self.resolve(attachment_id); p.unlink(); return {'id':attachment_id,'deleted':True}
    def resolve(self, attachment_id):
        p=(self.root/Path(attachment_id).name).resolve()
        if self.root.resolve() not in p.parents: raise PermissionError('Invalid attachment path')
        if not p.exists(): raise FileNotFoundError(attachment_id)
        return p
    def to_message_part(self, attachment_id):
        p=self.resolve(attachment_id); data=p.read_bytes(); ctype=mimetypes.guess_type(p.name)[0] or 'application/octet-stream'
        if ctype in IMAGE_TYPES:
            encoded=base64.b64encode(data).decode('ascii')
            return {'type':'image_url','image_url':{'url':f'data:{ctype};base64,{encoded}'}}, None
        try:
            text=data.decode('utf-8')
            return {'type':'text','text':f'Attached file {p.name}:\n{text[:100000]}'}, text
        except UnicodeDecodeError:
            return {'type':'text','text':f'Attached binary file {p.name} ({ctype}, {len(data)} bytes).'}, None
