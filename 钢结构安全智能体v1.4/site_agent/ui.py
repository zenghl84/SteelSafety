import os,json,hashlib
import streamlit as st
from .client import DeepSeekClient,LLMError
from .agent import SiteSafetyAgent,fingerprint,KB
from .offline import OfflineSiteAgent
from partition_rom.core import load

def render_assistant(result):
    with st.sidebar:
        with st.expander('助手设置',expanded=False):
            mode=st.radio('助手模式',['离线助手（无需API）','在线 DeepSeek'],key='assistant_mode')
            offline=mode.startswith('离线')
            base=name=key=''
            if offline:
                connected=True
                st.caption('本地规则问答与POD计算，无需密钥，不调用大语言模型。')
            else:
                base=st.text_input('接口基础地址',value=os.getenv('DEEPSEEK_BASE_URL','https://api.deepseek.com'),key='llm_base')
                name=st.text_input('模型名称',value=os.getenv('DEEPSEEK_MODEL','deepseek-flash'),key='llm_name')
                key=st.text_input('API 密钥（仅当前会话）',value=os.getenv('DEEPSEEK_API_KEY',''),type='password',key='llm_key')
                connected=bool(key.strip() and name.strip() and base.strip())
                st.caption('在线模式向配置的服务商发送问题、近期对话和相关计算摘要；密钥不写入文件。')
                if st.button('测试连接',disabled=not connected):
                    try:
                        with st.spinner('测试接口…'):
                            DeepSeekClient(key,name,base).complete([{'role':'user','content':'请只回复：连接成功。'}])
                        st.session_state.llm_verified=hashlib.sha256((base+name+key).encode()).hexdigest()
                        st.success('连接测试成功。')
                    except LLMError as ex:st.error(str(ex))
                st.caption('已填写接口' if connected else '大模型未连接')
            show_evidence=st.checkbox('显示回答依据',value=False,key='show_chat_evidence')
            if st.button('清空对话'):
                st.session_state.site_messages=[];st.rerun()
            st.download_button('下载项目说明',KB,'project_knowledge.md')
    st.subheader('现场安全助手')
    st.caption('可问：当前计划有什么需要注意？为什么预警？查询杆件2081。')
    snapshot=result.get('agent_snapshot') if result else None
    current=(fingerprint(snapshot) if snapshot else 'invalid')+mode
    if st.session_state.get('agent_snapshot_id')!=current:
        st.session_state.site_messages=[];st.session_state.agent_snapshot_id=current
    if not connected:st.caption('请在侧栏“助手设置”填写接口信息，或切换离线助手。')
    question=st.chat_input('向安全助手提问……',disabled=not connected,max_chars=3000)
    if question:
        try:
            with st.spinner('正在分析…'):
                model,_=load()
                engine=OfflineSiteAgent(model) if offline else SiteSafetyAgent(DeepSeekClient(key,name,base),model)
                answer=engine.answer(question,snapshot,st.session_state.site_messages,'管理人员')
            import uuid
            st.session_state.site_messages.extend([{'role':'user','content':question},
                {'role':'assistant','content':answer['answer'],'evidence':answer['evidence'],'id':uuid.uuid4().hex}])
            st.session_state.site_messages=st.session_state.site_messages[-20:]
        except LLMError as ex:st.error(str(ex))
        except (ValueError,KeyError,TypeError,OSError):st.error('当前计算数据不可用，请核对计划与模型。')
    for msg in st.session_state.site_messages:
        with st.chat_message(msg['role']):
            st.markdown(msg['content'])
            if show_evidence and 'evidence' in msg:
                with st.expander('计算依据 [E1]'):
                    st.json(msg['evidence'])
                    st.download_button('下载依据',json.dumps(msg['evidence'],ensure_ascii=False,indent=2),
                        'assistant_evidence.json',key='evidence_'+msg['id'])
