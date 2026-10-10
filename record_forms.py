"""Additive default property definitions for record creation; preserve user definitions."""
def field(key,label,typ='text',options=None):
    value=dict(key=key,label=label,type=typ)
    if options is not None:value['options']=options
    return value

LIFECYCLE=['Subscriber','Lead','Marketing qualified lead','Sales qualified lead','Opportunity','Customer','Evangelist','Other']
PRIORITY=['Low','Medium','High','Urgent']
FIELDS={
 'contacts':[field('email','Email','email'),field('first_name','First name'),field('last_name','Last name'),field('job_title','Job title'),field('phone','Phone number'),field('lifecycle_stage','Lifecycle stage','select',LIFECYCLE),field('lead_status','Lead status','select',['New','Open','In progress','Open deal','Unqualified','Attempted to contact','Connected','Bad timing'])],
 'companies':[field('domain','Company domain name'),field('industry','Industry','select',['Agriculture','Construction','Education','Energy','Finance','Healthcare','Hospitality','Manufacturing','Professional services','Real estate','Retail','Technology','Transportation','Other']),field('company_type','Type','select',['Prospect','Customer','Partner','Vendor','Other']),field('city','City'),field('region','State / Region'),field('postal_code','Postal code'),field('employees','Number of employees','number'),field('annual_revenue','Annual revenue','number'),field('time_zone','Time zone'),field('linkedin_url','LinkedIn company page')],
 'deals':[field('amount','Amount','number'),field('close_date','Close date','date'),field('deal_type','Deal type','select',['New business','Existing business']),field('priority','Priority','select',PRIORITY)],
 'tickets':[field('source','Source','select',['Email','Phone','Chat','Web form','Other']),field('priority','Priority','select',PRIORITY),field('create_date','Create date','date')],
 'tasks':[field('task_type','Task type','select',['To-do','Call','Email']),field('priority','Priority','select',PRIORITY),field('queue','Queue'),field('due_date','Due date','date'),field('due_time','Due time'),field('reminder_preference','Reminder preference','select',['No reminder','At due time','15 minutes before','1 hour before','1 day before']),field('repeat_preference','Repeat preference','select',['Does not repeat','Daily','Weekly','Monthly'])]
}

def upgrade(settings):
    if settings.get('creation_schema_version',0)>=2:return False
    for typ in settings['types']:
        fields=typ.setdefault('fields',[]);keys={f['key'] for f in fields}
        fields.extend(dict(f) for f in FIELDS.get(typ['id'],[]) if f['key'] not in keys)
    settings['creation_schema_version']=2
    return True
