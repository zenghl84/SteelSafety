"""Chat Completions transport; no automatic retries or credential logging."""
import json
import urllib.request
import urllib.error
from urllib.parse import urlsplit
class LLMError(Exception):pass
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):return None
class DeepSeekClient:
    def __init__(self,key,model,base_url):
        self.key=key.strip();self.model=model.strip();self.base_url=base_url.strip().rstrip('/')
        u=urlsplit(self.base_url)
        if u.scheme!='https' or not u.netloc or u.username or u.password or u.query or u.fragment:
            raise LLMError('接口地址须为不含账号、查询参数的 HTTPS 地址。')
        if not self.key or not self.model:raise LLMError('请填写 API 密钥和模型名称。')
    def complete(self,messages,json_mode=False):
        body=dict(model=self.model,messages=messages,max_tokens=1800,stream=False)
        if urlsplit(self.base_url).hostname=='api.deepseek.com':body['thinking']={'type':'disabled'}
        if json_mode:body['response_format']={'type':'json_object'}
        req=urllib.request.Request(self.base_url+'/chat/completions',data=json.dumps(body,ensure_ascii=False).encode('utf-8'),
            headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'},method='POST')
        try:
            with urllib.request.build_opener(NoRedirect()).open(req,timeout=30) as res:
                payload=json.loads(res.read(2_000_000))
            choice=payload['choices'][0]
            if choice.get('finish_reason')=='length':raise LLMError('模型输出被截断，请缩短问题后重试。')
            result=choice['message']['content']
            if not isinstance(result,str) or not result.strip():raise LLMError('接口没有返回有效文本。')
            return result.replace(self.key,'[密钥已隐藏]')
        except urllib.error.HTTPError as e:
            labels={401:'密钥无效或未授权',402:'账户余额不足',403:'访问被拒绝',404:'接口或模型名称不存在',429:'请求过多或额度受限'}
            raise LLMError(f'接口请求失败（HTTP {e.code}）：'+labels.get(e.code,'请检查服务商状态与接口配置')) from None
        except LLMError:raise
        except Exception:raise LLMError('网络超时、连接失败或接口响应格式不兼容。原有预测功能不受影响。') from None
