import {api} from './base.js';
const path='/api/muster-drills';
export const drills=()=>api(path);
export const create=data=>api(path,'POST',data);
export const data=(code,section)=>api(`${path}/${encodeURIComponent(code)}/${section}`);
export const save=(code,section,body)=>api(`${path}/${encodeURIComponent(code)}/${section}`,section==='clock'?'PUT':'POST',body);
