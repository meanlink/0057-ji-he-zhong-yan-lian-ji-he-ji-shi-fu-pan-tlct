import {api} from './base.js';
const path='/api/muster-drills';
export const drills=()=>api(path);
export const create=data=>api(path,'POST',data);
export const data=(code,section)=>api(`${path}/${encodeURIComponent(code)}/${section}`);
export const save=(code,section,body)=>api(`${path}/${encodeURIComponent(code)}/${section}`,section==='clock'?'PUT':'POST',body);
export const corrections=code=>data(code,'corrections');
export const openCorrection=(code,body)=>api(`${path}/${encodeURIComponent(code)}/corrections`,'POST',body);
export const retryCorrection=(code,ticketId)=>api(`${path}/${encodeURIComponent(code)}/corrections/${ticketId}/retry`,'POST');
