import httpx
from app.config import settings
cfg=settings()
with httpx.Client(timeout=60) as client:
    response=client.get('https://generativelanguage.googleapis.com/v1beta/models',headers={'x-goog-api-key':cfg.gemini_api_key})
    models=response.json().get('models',[])
    print({'models':[{k:m.get(k) for k in ('name','supportedGenerationMethods')} for m in models if 'flash' in m['name']]})
    response=client.post(f'https://generativelanguage.googleapis.com/v1beta/models/{cfg.gemini_model}:generateContent',
        headers={'x-goog-api-key':cfg.gemini_api_key},json={'contents':[{'parts':[{'text':'Say hello.'}]}]})
    print({'status':response.status_code,'has_candidates':bool(response.json().get('candidates'))})
