import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../test/render-app';

const dashboard={selectedDate:'2026-08-13',timezone:'Europe/Stockholm',generatedAt:'2026-08-12T20:00:00Z',matchupSource:'missing',matches:[],matchups:[]};
function main(){return within(screen.getByRole('main'));}

describe('step 4 proof and operations status',()=>{
 it('shows persisted model/policy states without presenting row counts as proof',async()=>{
  renderApp('/modell',{
   '/api/v1/dashboard':dashboard,
   '/api/v1/model':{modelIds:['v6'],policyIds:['policy-a'],modelStatuses:['forward_test_only'],policyStatuses:['shadow'],scoreCount:120,forwardSelectionCount:18,settledForwardCount:7,officialClvCount:5},
  });
  expect(await main().findByRole('heading',{name:'Modell & proof'})).toBeInTheDocument();
  expect(main().getByText('Forward test only')).toBeInTheDocument();
  expect(main().getByText('Shadow')).toBeInTheDocument();
  expect(main().getByText(/antal observationer är inte proof/i)).toBeInTheDocument();
  expect(main().queryByText(/ev_model_scores|forward_bets|V2-collections/i)).not.toBeInTheDocument();
 });

 it('renders jobs, health and audits instead of hiding operations evidence',async()=>{
  renderApp('/systemstatus',{
   '/api/v1/dashboard':dashboard,
   '/api/v1/system':{
    jobs:[{run_id:'r1',job_name:'capture-job',source_workflow:'capture.yml',status:'succeeded',started_at:'2026-08-12T20:00:00Z',finished_at:'2026-08-12T20:02:00Z'}],
    health:[{check_name:'capture-health',status:'partial',generated_at:'2026-08-12T20:03:00Z',message:'T-10 coverage incomplete'}],
    audits:[{audit_name:'forward-proof',status:'unproven',generated_at:'2026-08-12T20:04:00Z',detail:'Forward sample not sufficient for proof'}],
   },
  });
  expect(await main().findByRole('heading',{name:'Systemstatus'})).toBeInTheDocument();
  expect(main().getByRole('heading',{name:'Senaste jobb'})).toBeInTheDocument();
  expect(main().getByRole('heading',{name:'Health'})).toBeInTheDocument();
  expect(main().getByRole('heading',{name:'Audits'})).toBeInTheDocument();
  expect(main().getByText('capture-health')).toBeInTheDocument();
  expect(main().getByText('PARTIAL')).toBeInTheDocument();
  expect(main().getByText('forward-proof')).toBeInTheDocument();
  expect(main().getByText('UNPROVEN')).toBeInTheDocument();
  expect(main().queryByText(/job_runs|health_reports|audit_reports/i)).not.toBeInTheDocument();
 });
});
