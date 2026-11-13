import json,time

def instrument(old,out):
    api=old.api
    def timed(path,*args,**kwargs):
        start=time.monotonic();row={'path':path,'started_at_unix':time.time()}
        if path=='/api/motion/plan':
            body=dict(args[0] if args else kwargs.get('body') or {})
            body['planning_mode']='FAST'
            args=(body,)+args[1:]
        try:
            value=api(path,*args,**kwargs);row['success']=True
            if isinstance(value,dict):
                row['plan_id']=value.get('plan_id');row['plan_artifact']=value.get('plan_artifact')
            return value
        except BaseException as e:
            row.update(success=False,error=str(e));raise
        finally:
            row['wall_s']=time.monotonic()-start
            with (out/'api-timings.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
    old.api=timed
