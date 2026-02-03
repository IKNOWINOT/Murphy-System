
import { MicroTaskSchema, AutomationSpecSchema } from '../../schema';
export function toMicroTasks(spec:any){
  const out:any[]=[]; const steps=spec?.steps||[];
  for(const s of steps){
    const success = s.action==='focus_app' ? {type:'window', selector:s.args?.app, timeout_s:10} :
                    s.action==='type' ? {type:'text', selector:'<screen_ocr>', timeout_s:10} :
                    s.action==='click' ? {type:'pixel', image:s.args?.image||'', timeout_s:10} :
                    {type:'noop', timeout_s:5};
    out.push({ id:`mt_${s.id}`, goal:`Perform ${s.action}`, preconditions:[], steps:[s], success });
  }
  return out;
}
