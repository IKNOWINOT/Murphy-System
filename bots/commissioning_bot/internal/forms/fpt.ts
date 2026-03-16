// src/clockwork/bots/commissioning_bot/internal/forms/fpt.ts
import { CommissioningPlanSchema } from '../../schema';

type CommissioningPlan = ReturnType<typeof CommissioningPlanSchema['parse']>;

export function makeFPTForms(plan: CommissioningPlan) {
  const forms: Array<{ filename:string; content:any }> = [];
  for (const proc of plan.procedures || []) {
    const content = {
      form_type: 'FPT',
      id: proc.id,
      title: proc.title,
      preconditions: proc.preconditions,
      steps: proc.steps.map(s => ({
        id: s.id,
        action: s.action,
        expected_effect: s.expected_effect || '',
        hold_s: s.hold_s || null,
        safety: s.safety || [],
        watch_points: s.watch_points || [],
        fields: [
          { key:'observed', label:'Observed Behavior', type:'text' },
          { key:'pass', label:'Pass?', type:'boolean' },
          { key:'notes', label:'Notes', type:'text' }
        ]
      })),
      acceptance: proc.acceptance,
      data_capture: proc.data_capture,
      signoff: [{ role:'CxA', name:'', date:'' }, { role:'Controls', name:'', date:'' }, { role:'Owner', name:'', date:'' }]
    };
    forms.push({ filename: `FPT_${proc.id}.json`, content });
  }
  return forms;
}
