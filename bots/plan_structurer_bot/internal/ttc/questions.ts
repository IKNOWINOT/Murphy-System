
export function ttcQuestions(goal:string, domain:string){
  const base = [
    { axis:'who', prompt:'Who are the primary users and stakeholders?', options:['Admins','Moderators','End-users','Developers','Customers'] },
    { axis:'what', prompt:'What are the core capabilities for MVP?', options:['Auth','Real-time chat','Voice/Video','Search','Notifications'] },
    { axis:'when', prompt:'When do you need the first usable version?', options:['2 weeks','1 month','Quarter','[ASSUMED]'] },
    { axis:'where', prompt:'Where will it run or be distributed?', options:['Web','iOS','Android','Desktop','Region-specific'] },
    { axis:'how', prompt:'How should it be built? Any stack/integrations?', options:['React','Next.js','Postgres','WebRTC','Stripe','[ASSUMED]'] },
    { axis:'why', prompt:'Why is this important? What KPIs define success?', options:['DAU/WAU','Latency','Uptime','Revenue','Retention'] }
  ];
  // domain tweaks
  return base;
}
