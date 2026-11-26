import {appPath} from "./base-path";

export class RequestError extends Error {
  constructor(message:string,public status=0,public code="network_connection",public requestId="",public retryable=false){super(message+(requestId?`\n오류번호: ${requestId}`:""));this.name="RequestError";}
}
const fallback:Record<number,[string,string]>={
  401:["session_expired","로그인이 만료되었습니다. 작성 내용은 유지됩니다. 다시 로그인해 주세요."],
  403:["access_denied","요청 권한이나 세션을 확인하지 못했습니다. 다시 로그인한 뒤 시도해 주세요."],
  409:["revision_conflict","기록이 변경되었거나 임시 작업이 만료되었습니다. 작성 내용을 유지한 채 목록을 확인해 주세요."],
  413:["file_size","사진 용량 제한을 초과했습니다. 각 20MB 이하로 등록해 주세요."],
  422:["invalid_input","입력한 항목과 파일 형식을 확인해 주세요."],
  429:["rate_limit","요청이 많습니다. 잠시 후 다시 시도해 주세요."],
  502:["upstream_error","외부 연동 서비스가 응답하지 않았습니다. 입력을 유지한 채 다시 시도해 주세요."],
  503:["service_unavailable","서버 또는 외부 연동 서비스가 일시적으로 응답하지 않습니다. 입력을 유지한 채 다시 시도해 주세요."],
  504:["upstream_timeout","응답 대기시간을 초과했습니다. 입력을 유지한 채 다시 시도해 주세요."],
};
export function aborted(error:unknown){return error instanceof DOMException&&error.name==="AbortError";}
export async function requestApi(path:string,body:object|FormData|undefined,csrf:string,signal?:AbortSignal):Promise<Response>{
  const attempts=body?1:2;
  for(let attempt=0;attempt<attempts;attempt++){
    const controller=new AbortController();
    const stop=()=>controller.abort(signal?.reason);signal?.addEventListener("abort",stop,{once:true});
    if(signal?.aborted)stop();
    let timedOut=false;
    const timer=setTimeout(()=>{timedOut=true;controller.abort();},body?210000:35000);
    try{
      const form=body instanceof FormData;
      const response=await fetch(appPath(`/api${path}`),{credentials:"same-origin",cache:"no-store",signal:controller.signal,
        method:body?"POST":"GET",headers:body?{"X-CSRF-Token":csrf,...(form?{}:{"Content-Type":"application/json"})}:{},
        body:body?(form?body:JSON.stringify(body)):undefined});
      const bytes=await response.blob();
      const res=new Response(bytes,{status:response.status,headers:response.headers});
      if(res.ok)return res;
      const data=await res.json().catch(()=>({}));
      const [code,message]=fallback[res.status]||["request_failed","작업을 처리하지 못했습니다. 오류번호를 운영 담당자에게 알려주세요."];
      throw new RequestError(typeof data.detail==="string"?data.detail:message,res.status,data.code||code,data.request_id||res.headers.get("X-Request-ID")||"",[502,503,504].includes(res.status)&&data.retryable!==false);
    }catch(error){
      if(signal?.aborted)throw new DOMException("이전 조회를 취소했습니다.","AbortError");
      const problem=error instanceof RequestError?error:new RequestError(timedOut?"응답 대기시간을 초과했습니다. 입력을 유지한 채 다시 시도해 주세요.":"네트워크 연결을 확인해 주세요. 입력 내용은 유지됩니다.",timedOut?504:0,timedOut?"timeout":"network_connection","",true);
      if(attempt===attempts-1||!problem.retryable)throw problem;
    }finally{clearTimeout(timer);signal?.removeEventListener("abort",stop);}
    await new Promise<void>(resolve=>setTimeout(resolve,500));
  }
  throw new RequestError("연결을 다시 확인해 주세요.");
}
