"""Additive default property definitions for record creation; preserve user definitions."""
def field(key,label,typ='text',options=None):
    value=dict(key=key,label=label,type=typ)
    if options is not None:value['options']=options
    return value

LIFECYCLE=['Subscriber','Lead','Marketing qualified lead','Sales qualified lead','Opportunity','Customer','Evangelist','Other']
PRIORITY=['Low','Medium','High','Urgent']
FIELDS={
 'contacts':[field('email','Email','email'),field('first_name','First name'),field('last_name','Last name'),field('job_title','Job title'),field('phone','Phone number'),field('lifecycle_stage','Lifecycle stage','select',LIFECYCLE),field('lead_status','Lead status','select',['New','Open','In progress','Open deal','Unqualified','Attempted to contact','Connected','Bad timing'])],
 'companies':[field('domain','Company domain name'),field('phone','Phone number'),field('industry','Industry','select',['Agriculture','Construction','Education','Energy','Finance','Healthcare','Hospitality','Manufacturing','Professional services','Real estate','Retail','Technology','Transportation','Other']),field('company_type','Type','select',['Prospect','Customer','Partner','Vendor','Other']),field('city','City'),field('region','State / Region'),field('postal_code','Postal code'),field('employees','Number of employees','number'),field('annual_revenue','Annual revenue','number'),field('time_zone','Time zone'),field('linkedin_url','LinkedIn company page')],
 'deals':[field('amount','Amount','number'),field('close_date','Close date','date'),field('deal_type','Deal type','select',['New business','Existing business']),field('priority','Priority','select',PRIORITY)],
 'tickets':[field('ticket_status','Ticket status','select',['New','In progress','Waiting on customer','Closed']),field('source','Source','select',['Email','Phone','Chat','Web form','Other']),field('priority','Priority','select',PRIORITY),field('create_date','Create date','date')],
 'tasks':[field('completed','Completed','checkbox'),field('task_type','Task type','select',['To-do','Call','Email']),field('priority','Priority','select',PRIORITY),field('queue','Queue'),field('due_date','Due date','date'),field('due_time','Due time'),field('reminder_preference','Reminder preference','select',['No reminder','At due time','15 minutes before','1 hour before','1 day before']),field('repeat_preference','Repeat preference','select',['Does not repeat','Daily','Weekly','Monthly'])]
}

ENRICHMENT_FIELDS={
 'contacts':[field('linkedin_url','LinkedIn profile'),field('email_status','Email verification status'),field('city','City'),field('region','State / Region'),field('country','Country'),field('employer_name','Employer'),field('employer_domain','Employer domain'),field('seniority','Seniority'),field('department','Department')],
 'companies':[field('country','Country'),field('industry_text','Industry detail'),field('employee_range','Employee range'),field('estimated_annual_revenue','Estimated annual revenue','number'),field('revenue_range','Revenue range')]
}
def upgrade(settings):
    version=settings.get('creation_schema_version',0)
    if version>=7:return False
    for typ in settings['types']:
        fields=typ.setdefault('fields',[]);keys={f['key'] for f in fields}
        additions=(FIELDS.get(typ['id'],[]) if version<3 else [])+(ENRICHMENT_FIELDS.get(typ['id'],[]) if version<4 else [])
        if version<7 and typ['id']=='deals':additions+=[field('loss_reason','Closed lost reason')]
        if version<6 and typ['id']=='tickets':additions+=[FIELDS['tickets'][0]]
        if typ['id']=='contacts':additions+=[field('email_tracking_disabled','Exclude from email open tracking','checkbox')]
        for f in additions:
            if f['key'] not in keys:
                fields.append(dict(f));keys.add(f['key'])
    settings['creation_schema_version']=7
    return True
