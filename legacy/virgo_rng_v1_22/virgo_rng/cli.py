import argparse
import json
from pathlib import Path
from .core import acquire
from .analysis import analyze_file, write_json
from .extract import condition_file
from .health import health_file
from .compare import compare_files
from .advanced import diagnose, plot_report
from .stream import capture_stream, process_stream
from .generator import generate_file, generate_live, HealthMonitor
from .validation import window_diagnostics, binary_tests, plot_windows, save_report
from .transients import transient_report, plot_transients
from .research09 import research_report, campaign_summary, plot_dashboard

def main():
    p=argparse.ArgumentParser(description='Virgo-RNG v1.11: research only, NOT cryptographically validated')
    sub=p.add_subparsers(dest='command',required=True)
    cap=sub.add_parser('capture',help='Capture RTL-SDR I/Q (requires pyrtlsdr)')
    cap.add_argument('--seconds',type=float,default=10)
    cap.add_argument('--rate',type=int,default=2400000)
    cap.add_argument('--freq',type=int,default=1420405752)
    cap.add_argument('--gain',type=float)
    cap.add_argument('--out',type=Path,required=True)
    cap.add_argument('--setup',choices=['indoor-dipole','external-antenna','50ohm-termination','other','unknown'],default='unknown')
    ana=sub.add_parser('analyze',help='Offline diagnostics on cu8 file')
    ana.add_argument('file',type=Path)
    ana.add_argument('--report',type=Path)
    ana.add_argument('--max-lag',type=int,default=64)
    ana.add_argument('--window-samples',type=int,default=1000000)
    ana.add_argument('--setup',choices=['indoor-dipole','external-antenna','50ohm-termination','other','unknown'],default='unknown')
    ext=sub.add_parser('extract',help='Experimental SHA-256 conditioning (NOT secure/validated)')
    ext.add_argument('file',type=Path)
    ext.add_argument('--out',type=Path,required=True)
    ext.add_argument('--block-bytes',type=int,default=4096)
    h=sub.add_parser('health',help='Offline heuristic health diagnostics (not NIST certified)')
    h.add_argument('file',type=Path)
    h.add_argument('--report',type=Path)
    h.add_argument('--window-bytes',type=int,default=65536)
    h.add_argument('--repetition-cutoff',type=int,default=32)
    h.add_argument('--proportion-cutoff',type=float,default=0.10)
    cmp=sub.add_parser('compare',help='Compare two cu8 recordings')
    cmp.add_argument('first',type=Path)
    cmp.add_argument('second',type=Path)
    cmp.add_argument('--report',type=Path,required=True)
    cmp.add_argument('--max-lag',type=int,default=64)
    cmp.add_argument('--window-samples',type=int,default=1000000)
    adv=sub.add_parser('advanced',help='Offline PSD and one-step prediction diagnostics (NOT validated entropy)')
    adv.add_argument('file',type=Path)
    adv.add_argument('--rate',type=int,default=2400000)
    adv.add_argument('--fft-size',type=int,default=4096)
    adv.add_argument('--max-pairs',type=int,default=1000000)
    adv.add_argument('--report',type=Path,required=True)
    adv.add_argument('--plot',type=Path,help='Optional PNG; install .[plot]')
    st=sub.add_parser('stream',help='Bounded-memory RTL-SDR acquisition using rtl_sdr executable')
    st.add_argument('--seconds',type=float,default=10)
    st.add_argument('--rate',type=int,default=2400000)
    st.add_argument('--freq',type=int,default=1420405752)
    st.add_argument('--gain',type=float,default=None)
    st.add_argument('--out',type=Path,required=True)
    st.add_argument('--report',type=Path,required=True)
    st.add_argument('--chunk-bytes',type=int,default=262144)
    st.add_argument('--setup',choices=['indoor-dipole','external-antenna','50ohm-termination','other','unknown'],default='unknown')
    offline=sub.add_parser('stream-file',help='Exercise streaming diagnostics on an existing CU8 file')
    offline.add_argument('file',type=Path)
    offline.add_argument('--out',type=Path,required=True)
    offline.add_argument('--report',type=Path,required=True)
    offline.add_argument('--chunk-bytes',type=int,default=262144)
    offline.add_argument('--setup',choices=['indoor-dipole','external-antenna','50ohm-termination','other','unknown'],default='unknown')
    gen=sub.add_parser('generate-file',help='Research-only conditioned stream from existing CU8; FAIL CLOSED')
    gen.add_argument('file',type=Path)
    gen.add_argument('--out',type=Path,required=True)
    gen.add_argument('--report',type=Path,required=True)
    gen.add_argument('--block-bytes',type=int,default=4096)
    gen.add_argument('--setup',choices=['indoor-dipole','external-antenna','50ohm-termination','other','unknown'],default='unknown')
    live=sub.add_parser('generate-live',help='Research-only conditioned stream from rtl_sdr; FAIL CLOSED')
    live.add_argument('--seconds',type=float,default=10)
    live.add_argument('--rate',type=int,default=2400000)
    live.add_argument('--freq',type=int,default=1420405752)
    live.add_argument('--gain',type=float)
    live.add_argument('--out',type=Path,required=True)
    live.add_argument('--report',type=Path,required=True)
    live.add_argument('--block-bytes',type=int,default=4096)
    live.add_argument('--setup',choices=['indoor-dipole','external-antenna','50ohm-termination','other','unknown'],default='unknown')
    v=sub.add_parser('validate-source',help='Exploratory window statistics and held-out Markov predictor; NOT SP 800-90B')
    v.add_argument('file',type=Path)
    v.add_argument('--report',type=Path,required=True)
    v.add_argument('--plot',type=Path)
    v.add_argument('--channel',choices=['i','q'],default='i')
    v.add_argument('--max-bytes',type=int,default=4000000)
    v.add_argument('--skip-bytes',type=int,default=0)
    v.add_argument('--window-samples',type=int,default=65536)
    bt=sub.add_parser('test-bits',help='Exploratory frequency/runs/correlation checks on binary output')
    bt.add_argument('file',type=Path)
    bt.add_argument('--report',type=Path,required=True)
    bt.add_argument('--max-bytes',type=int,default=8000000)
    tr=sub.add_parser('transients',help='Inspect startup drift without automatically discarding data')
    tr.add_argument('file',type=Path)
    tr.add_argument('--channel',choices=['i','q'],default='i')
    tr.add_argument('--max-bytes',type=int,default=4000000)
    tr.add_argument('--skip-bytes',type=int,default=0)
    tr.add_argument('--window-samples',type=int,default=4096)
    tr.add_argument('--report',type=Path,required=True)
    tr.add_argument('--plot',type=Path)
    r9=sub.add_parser('research09',help='Held-out history predictors, robust change flags, and dashboard')
    r9.add_argument('file',type=Path)
    r9.add_argument('--channel',choices=['i','q'],default='i')
    r9.add_argument('--max-bytes',type=int,default=2000000)
    r9.add_argument('--skip-bytes',type=int,default=0)
    r9.add_argument('--window-samples',type=int,default=16384)
    r9.add_argument('--report',type=Path,required=True)
    r9.add_argument('--plot',type=Path)
    campaign=sub.add_parser('campaign09',help='Summarize multiple v0.9 research reports')
    campaign.add_argument('reports',type=Path,nargs='+')
    campaign.add_argument('--out',type=Path,required=True)
    dash=sub.add_parser('dashboard',help='Local interactive I/Q dashboard (offline playback or RTL-SDR)')
    source=dash.add_mutually_exclusive_group(required=True)
    source.add_argument('--file',type=Path)
    source.add_argument('--live',action='store_true')
    dash.add_argument('--rate',type=int,default=2400000)
    dash.add_argument('--freq',type=int,default=1420405752)
    dash.add_argument('--gain',type=float)
    dash.add_argument('--seconds',type=float,default=30)
    dash.add_argument('--chunk-bytes',type=int,default=65536)
    dash.add_argument('--interval',type=float,default=0.05,help='Playback delay per window (file only)')
    dash.add_argument('--port',type=int,default=8765)
    dash.add_argument('--open-browser',action='store_true')
    dash.add_argument('--setup',choices=['indoor-dipole','external-antenna','50ohm-termination','other','unknown'],default='unknown')
    prep=sub.add_parser('nist-prepare',help='Demultiplex CU8 into raw I and Q symbol files for official NIST tools')
    prep.add_argument('file',type=Path)
    prep.add_argument('--out-dir',type=Path,required=True)
    prep.add_argument('--skip-pairs',type=int,default=0)
    prep.add_argument('--max-pairs',type=int)
    prep.add_argument('--setup',choices=['indoor-dipole','external-antenna','50ohm-termination','other','unknown'],default='unknown')
    nist=sub.add_parser('nist-run',help='Run externally installed official NIST executable on byte-encoded symbols')
    nist.add_argument('file',type=Path)
    nist.add_argument('--binary',default='ea_non_iid')
    nist.add_argument('--bits-per-symbol',type=int,default=8)
    nist.add_argument('--timeout',type=int,default=3600)
    nist.add_argument('--report',type=Path,required=True)
    campaign12=sub.add_parser('nist-campaign',help='Prepare beginning/middle/end I,Q and interleaved IQ NIST inputs')
    campaign12.add_argument('file',type=Path)
    campaign12.add_argument('--out-dir',type=Path,required=True)
    campaign12.add_argument('--pairs-per-segment',type=int,default=1000000)
    campaign12.add_argument('--setup',default='unknown')
    campaign12.add_argument('--reference-i',type=Path)
    campaign12.add_argument('--reference-q',type=Path)
    campaign12.add_argument('--binary',help='Optional path to official ea_non_iid; runs all prepared inputs')
    campaign12.add_argument('--timeout',type=int,default=3600)
    summarize12=sub.add_parser('nist-campaign-summary',help='Summarize reference outputs generated by nist-campaign')
    summarize12.add_argument('directory',type=Path)
    summarize12.add_argument('--out',type=Path,required=True)
    screen=sub.add_parser('nist-screen',help='Prepare 3 raw within-recording I/Q segments for official NIST non-IID screening')
    screen.add_argument('file',type=Path)
    screen.add_argument('--out-dir',type=Path,required=True)
    screen.add_argument('--pairs-per-segment',type=int,default=1000000)
    screen.add_argument('--setup',default='unknown')
    screen.add_argument('--binary',help='Optional official ea_non_iid executable; runs six assessments')
    screen.add_argument('--timeout',type=int,default=3600)
    screen_eval=sub.add_parser('nist-screen-evaluate',help='Run official ea_non_iid on prepared screening inputs')
    screen_eval.add_argument('directory',type=Path)
    screen_eval.add_argument('--binary',required=True)
    screen_eval.add_argument('--timeout',type=int,default=3600)
    restart=sub.add_parser('restart-collect',help='Collect independent startup CU8 captures; physical reset MUST be verified externally')
    restart.add_argument('--out-dir',type=Path,required=True)
    restart.add_argument('--runs',type=int,default=1000)
    restart.add_argument('--samples',type=int,default=1000,help='IQ pairs per restart')
    restart.add_argument('--rate',type=int,default=2400000)
    restart.add_argument('--freq',type=int,default=1420405752)
    restart.add_argument('--gain',type=float,default=30)
    restart.add_argument('--device',type=int,default=0)
    restart.add_argument('--rtl-binary',default='rtl_sdr')
    restart.add_argument('--restart-command',help='External hardware power-cycle command, shell-free; no guarantee of real reset')
    restart.add_argument('--manual',action='store_true',help='Prompt for confirmed physical power cycle before EACH capture')
    restart.add_argument('--setup',default='unknown')
    restart.add_argument('--timeout',type=int,default=30)
    pack=sub.add_parser('restart-pack',help='Verify complete run set and build I/Q row-major matrices')
    pack.add_argument('directory',type=Path)
    audit=sub.add_parser('restart-audit',help='Audit restart journal, capture hashes and packed matrices')
    audit.add_argument('directory',type=Path)
    audit.add_argument('--require-full',action='store_true')
    audit.add_argument('--report',type=Path)
    rr=sub.add_parser('restart-evaluate',help='Run official NIST ea_restart on VERIFIED 1000x1000 physical restart matrices')
    rr.add_argument('directory',type=Path)
    rr.add_argument('--binary',default='ea_restart')
    rr.add_argument('--h-i',type=float,required=True,help='Documented initial non-IID estimate for I; Q uses --h-q when supplied')
    rr.add_argument('--h-q',type=float,help='Separate initial estimate for Q (defaults to --h-i)')
    rr.add_argument('--timeout',type=int,default=3600)
    rr.add_argument('--ack-physical-restarts',action='store_true',help='Operator attests 1000 actual hardware power cycles; not established by software')
    rr.add_argument('--report-dir',type=Path)
    startup=sub.add_parser('startup-collect',help='Characterize first rtl_sdr-delivered I/Q samples after operator-attested physical reset')
    startup.add_argument('--out-dir',type=Path,required=True)
    startup.add_argument('--runs',type=int,default=3)
    startup.add_argument('--pairs',type=int,default=262144)
    startup.add_argument('--block-pairs',type=int,default=4096)
    startup.add_argument('--rate',type=int,default=2400000)
    startup.add_argument('--freq',type=int,default=1420405752)
    startup.add_argument('--gain',type=float,default=30)
    startup.add_argument('--device',type=int,default=0)
    startup.add_argument('--rtl-binary',default='rtl_sdr')
    startup.add_argument('--setup',default='unknown',help='e.g. indoor-dipole or 50ohm-termination')
    startup.add_argument('--timeout',type=int,default=40)
    startup.add_argument('--no-plot',action='store_true')
    review=sub.add_parser('startup-analyze',help='Reanalyze existing startup campaign with SHA256 checks')
    review.add_argument('directory',type=Path)
    review.add_argument('--block-pairs',type=int)
    review.add_argument('--no-plot',action='store_true')
    temporal=sub.add_parser('temporal-capture',help='One continuous bounded RTL-SDR capture, no USB restarts')
    temporal.add_argument('--out-dir',type=Path,required=True)
    temporal.add_argument('--seconds',type=float,default=180)
    temporal.add_argument('--rate',type=int,default=2400000)
    temporal.add_argument('--freq',type=int,default=1420405752)
    temporal.add_argument('--gain',type=float,default=30)
    temporal.add_argument('--device',type=int,default=0)
    temporal.add_argument('--window-seconds',type=float,default=1.0)
    temporal.add_argument('--setup',choices=['indoor-dipole','50ohm-termination','other'],default='indoor-dipole')
    temporal.add_argument('--no-plot',action='store_true')
    temporal_file=sub.add_parser('temporal-analyze',help='Analyze existing continuous CU8 without receiver')
    temporal_file.add_argument('file',type=Path)
    temporal_file.add_argument('--out-dir',type=Path,required=True)
    temporal_file.add_argument('--rate',type=int,default=2400000)
    temporal_file.add_argument('--window-seconds',type=float,default=1.0)
    temporal_file.add_argument('--no-plot',action='store_true')
    dep=sub.add_parser('iq-dependence',help='Offline I/Q joint entropy, mutual information and lag correlations')
    dep.add_argument('file',type=Path)
    dep.add_argument('--out-dir',type=Path,required=True)
    dep.add_argument('--chunk-pairs',type=int,default=1000000)
    dep.add_argument('--lag-pairs',type=int,default=200000)
    dep.add_argument('--max-lag',type=int,default=32)
    dep.add_argument('--no-plot',action='store_true')
    td=sub.add_parser('temporal-dependence',help='Offline conditional Shannon entropy over time')
    td.add_argument('file',type=Path)
    td.add_argument('--out-dir',type=Path,required=True)
    td.add_argument('--rate',type=int,default=2400000)
    td.add_argument('--window-seconds',type=float,default=1.0)
    td.add_argument('--sample-pairs',type=int,default=200000)
    td.add_argument('--no-plot',action='store_true')
    pred=sub.add_parser('predictive-dependence',help='Offline chronological holdout predictive dependence, 4-bit channels')
    pred.add_argument('file',type=Path)
    pred.add_argument('--out-dir',type=Path,required=True)
    pred.add_argument('--rate',type=int,default=2400000)
    pred.add_argument('--window-seconds',type=float,default=1.0)
    pred.add_argument('--sample-pairs',type=int,default=120000)
    pred.add_argument('--windows',type=int,default=12)
    pred.add_argument('--no-plot',action='store_true')
    joint=sub.add_parser('joint-predictive',help='Joint I/Q predictive model with backoff and shuffled-pair controls')
    joint.add_argument('file',type=Path)
    joint.add_argument('--out-dir',type=Path,required=True)
    joint.add_argument('--rate',type=int,default=2400000)
    joint.add_argument('--window-seconds',type=float,default=1.0)
    joint.add_argument('--sample-pairs',type=int,default=120000)
    joint.add_argument('--windows',type=int,default=12)
    joint.add_argument('--shuffle-repeats',type=int,default=3)
    joint.add_argument('--quantization-bits',type=int,choices=[1,2],default=2)
    joint.add_argument('--no-plot',action='store_true')
    cross=sub.add_parser('cross-channel',help='Measure incremental predictive value of the other I/Q channel')
    cross.add_argument('file',type=Path)
    cross.add_argument('--out-dir',type=Path,required=True)
    cross.add_argument('--rate',type=int,default=2400000)
    cross.add_argument('--window-seconds',type=float,default=1.0)
    cross.add_argument('--sample-pairs',type=int,default=120000)
    cross.add_argument('--windows',type=int,default=12)
    cross.add_argument('--shuffle-repeats',type=int,default=3)
    cross.add_argument('--no-plot',action='store_true')
    lag=sub.add_parser('lag-mi',help='Lagged I/Q mutual information with circular-shift controls')
    lag.add_argument('file',type=Path)
    lag.add_argument('--out-dir',type=Path,required=True)
    lag.add_argument('--rate',type=int,default=2400000)
    lag.add_argument('--window-seconds',type=float,default=1.0)
    lag.add_argument('--sample-pairs',type=int,default=120000)
    lag.add_argument('--windows',type=int,default=12)
    lag.add_argument('--max-lag',type=int,default=32)
    lag.add_argument('--quantization-bits',type=int,choices=[2,3,4,5,6,7,8],default=4)
    lag.add_argument('--control-repeats',type=int,default=10)
    lag.add_argument('--seed',type=int,default=115)
    lag.add_argument('--no-plot',action='store_true')
    glob=sub.add_parser('global-lag-mi',help='Global max-lag I/Q mutual-information test with shifted null')
    glob.add_argument('file',type=Path)
    glob.add_argument('--out-dir',type=Path,required=True)
    glob.add_argument('--rate',type=int,default=2400000)
    glob.add_argument('--window-seconds',type=float,default=1.0)
    glob.add_argument('--sample-pairs',type=int,default=30000)
    glob.add_argument('--windows',type=int,default=12)
    glob.add_argument('--max-lag',type=int,default=32)
    glob.add_argument('--quantization-bits',type=int,choices=[2,3,4,5,6,7,8],default=4)
    glob.add_argument('--permutations',type=int,default=199)
    glob.add_argument('--seed',type=int,default=116)
    glob.add_argument('--no-plot',action='store_true')
    args=p.parse_args()
    if args.command=='global-lag-mi':
        from .global_lag_mi116 import global_test
        result=global_test(args.file,out_dir=args.out_dir,rate=args.rate,
            window_seconds=args.window_seconds,sample_pairs=args.sample_pairs,
            windows=args.windows,max_lag=args.max_lag,quantization_bits=args.quantization_bits,
            permutations=args.permutations,seed=args.seed,plot=not args.no_plot)
        print(json.dumps({'global_test':result['global_test'],
            'report':str(args.out_dir/'global_lag_mi_report.json')},indent=2))
    elif args.command=='lag-mi':
        from .lag_mi115 import analyze_file as lag_analyze
        result=lag_analyze(args.file,out_dir=args.out_dir,rate=args.rate,window_seconds=args.window_seconds,
            sample_pairs=args.sample_pairs,windows=args.windows,max_lag=args.max_lag,
            quantization_bits=args.quantization_bits,control_repeats=args.control_repeats,
            seed=args.seed,plot=not args.no_plot)
        print(json.dumps({'summary':{'max_excess_lag':result['summary']['max_excess_lag'],
            'max_excess_bits':result['summary']['max_excess_bits']},
            'report':str(args.out_dir/'lag_mi_report.json')},indent=2))
    elif args.command=='cross-channel':
        from .cross_channel114 import analyze_file
        result=analyze_file(args.file,out_dir=args.out_dir,rate=args.rate,window_seconds=args.window_seconds,
            sample_pairs=args.sample_pairs,windows=args.windows,shuffle_repeats=args.shuffle_repeats,plot=not args.no_plot)
        print(json.dumps({'summary':result['summary'],'report':str(args.out_dir/'cross_channel_report.json')},indent=2))
    elif args.command=='joint-predictive':
        from .joint_predictive112 import analyze_file as joint_analyze
        result=joint_analyze(args.file,out_dir=args.out_dir,rate=args.rate,window_seconds=args.window_seconds,
            sample_pairs=args.sample_pairs,windows=args.windows,shuffle_repeats=args.shuffle_repeats,
            quantization_bits=args.quantization_bits,plot=not args.no_plot)
        print(json.dumps({'summary':result['summary'],'report':str(args.out_dir/'joint_predictive_report.json')},indent=2))
    elif args.command=='predictive-dependence':
        from .predictive111 import analyze_file as predictive_analyze
        result=predictive_analyze(args.file,out_dir=args.out_dir,rate=args.rate,window_seconds=args.window_seconds,sample_pairs=args.sample_pairs,windows=args.windows,plot=not args.no_plot)
        print(json.dumps({'summary':result['summary'],'report':str(args.out_dir/'predictive_report.json')},indent=2))
    elif args.command=='temporal-dependence':
        from .temporal_dependence110 import analyze_file
        result=analyze_file(args.file,out_dir=args.out_dir,rate=args.rate,window_seconds=args.window_seconds,sample_pairs=args.sample_pairs,plot=not args.no_plot)
        print(json.dumps({'summary':result['summary'],'report':str(args.out_dir/'temporal_dependence_report.json')},indent=2))
    elif args.command=='iq-dependence':
        from .dependence19 import analyze_file as dependence_analyze
        result=dependence_analyze(args.file,out_dir=args.out_dir,chunk_pairs=args.chunk_pairs,lag_pairs=args.lag_pairs,max_lag=args.max_lag,plot=not args.no_plot)
        print(json.dumps({'shannon_bits':result['shannon_bits'],'cross_correlation_lag0':result['cross_correlation_lag0'],'report':str(args.out_dir/'dependence_report.json')},indent=2))
    elif args.command=='temporal-capture':
        from .temporal18 import capture
        result=capture(args.out_dir,seconds=args.seconds,rate=args.rate,freq=args.freq,gain=args.gain,device=args.device,window_seconds=args.window_seconds,setup=args.setup,plot=not args.no_plot)
        print(json.dumps(result,indent=2))
    elif args.command=='temporal-analyze':
        from .temporal18 import analyze_file
        result=analyze_file(args.file,rate=args.rate,window_pairs=int(args.rate*args.window_seconds),output=args.out_dir,plot=not args.no_plot)
        print(json.dumps({'windows_analyzed':result['windows_analyzed'],'report':str(args.out_dir/'temporal_report.json')},indent=2))
    elif args.command=='startup-collect':
        from .startup16 import collect
        report=collect(args.out_dir,runs=args.runs,pairs=args.pairs,block_pairs=args.block_pairs,
                       rate=args.rate,freq=args.freq,gain=args.gain,device=args.device,
                       rtl_binary=args.rtl_binary,setup=args.setup,timeout=args.timeout,
                       plot=not args.no_plot)
        print('Startup report:',args.out_dir/'startup_report.json','PLL warning runs:',report['pll_warning_runs'])
    elif args.command=='startup-analyze':
        from .startup16 import analyze_campaign
        report=analyze_campaign(args.directory,block_pairs=args.block_pairs,plot=not args.no_plot)
        print('Startup report:',args.directory/'startup_report.json','PLL warning runs:',report['pll_warning_runs'])
    elif args.command=='restart-audit':
        from .restart15 import audit
        result=audit(args.directory,require_full=args.require_full)
        if args.report:
            args.report.parent.mkdir(parents=True,exist_ok=True)
            args.report.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))
        if not result['integrity_ok']:
            raise SystemExit(2)
    elif args.command=='restart-evaluate':
        from .restart14 import evaluate
        reports=evaluate(args.directory,binary=args.binary,h_i=args.h_i,h_q=args.h_q,timeout=args.timeout,
                         ack_physical_restarts=args.ack_physical_restarts,report_dir=args.report_dir)
        print('Reference reports:',reports)
    elif args.command=='restart-collect':
        from .restart13 import collect
        result=collect(args.out_dir,runs=args.runs,samples=args.samples,rate=args.rate,freq=args.freq,
                       gain=args.gain,device=args.device,rtl_binary=args.rtl_binary,
                       restart_command=args.restart_command,manual=args.manual,setup=args.setup,timeout=args.timeout)
        print('Captured:',result['completed'],'restart sessions. Run restart-pack next.')
    elif args.command=='restart-pack':
        from .restart13 import pack
        result=pack(args.directory)
        print('Verified and packed:',result['outputs'])
    elif args.command=='nist-screen':
        from .nist_screen113 import prepare, evaluate
        result=prepare(args.file,args.out_dir,pairs=args.pairs_per_segment,setup=args.setup)
        print('Prepared',len(result['entries']),'raw symbol files:',args.out_dir)
        if args.binary:
            summary=evaluate(args.out_dir,binary=args.binary,timeout=args.timeout)
            print('Official evaluations completed:',summary['all_completed'])
    elif args.command=='nist-screen-evaluate':
        from .nist_screen113 import evaluate
        summary=evaluate(args.directory,binary=args.binary,timeout=args.timeout)
        print('Official evaluations completed:',summary['all_completed'])
    elif args.command=='nist-campaign':
        from .nist_campaign import prepare_campaign, execute_campaign
        manifest=prepare_campaign(args.file,args.out_dir,pairs_per_segment=args.pairs_per_segment,
                                  setup=args.setup,reference_i=args.reference_i,reference_q=args.reference_q)
        if args.binary: execute_campaign(args.out_dir,binary=args.binary,timeout=args.timeout)
        print('Prepared',len(manifest['inputs']),'NIST inputs:',args.out_dir)
    elif args.command=='nist-campaign-summary':
        from .nist_campaign import summarize_campaign
        result=summarize_campaign(args.directory)
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(result,indent=2)+'\n')
        print('Saved:',args.out)
    elif args.command=='nist-prepare':
        from .nist90b import prepare_cu8
        manifest=prepare_cu8(args.file,args.out_dir,skip_pairs=args.skip_pairs,max_pairs=args.max_pairs,setup=args.setup)
        print('Prepared',manifest['samples_per_channel'],'samples/channel; manifest:',args.out_dir/'manifest.json')
    elif args.command=='nist-run':
        from .nist90b import run_nist
        run_nist(args.file,args.report,binary=args.binary,bits_per_symbol=args.bits_per_symbol,timeout=args.timeout)
        print('Saved reference tool output:',args.report)
    elif args.command=='dashboard':
        from .dashboard import Monitor, serve
        monitor=Monitor(source=args.file,live=args.live,rate=args.rate,freq=args.freq,
                        gain=args.gain,seconds=args.seconds,chunk_bytes=args.chunk_bytes,
                        interval=args.interval,setup=args.setup)
        serve(monitor,port=args.port,open_browser=args.open_browser)
    elif args.command=='research09':
        result=research_report(args.file,channel=args.channel,max_bytes=args.max_bytes,
                               window_samples=args.window_samples,skip_bytes=args.skip_bytes)
        save_report(args.report,result)
        if args.plot: plot_dashboard(result,args.plot)
        print('Saved v0.9 research report',args.report)
    elif args.command=='campaign09':
        save_report(args.out,campaign_summary(args.reports))
        print('Saved campaign summary',args.out)
    elif args.command=='transients':
        result=transient_report(args.file,channel=args.channel,max_bytes=args.max_bytes,skip_bytes=args.skip_bytes,window_samples=args.window_samples)
        save_report(args.report,result)
        if args.plot: plot_transients(result,args.plot)
        print('Saved transient diagnostic',args.report)
    elif args.command=='validate-source':
        result=window_diagnostics(args.file,channel=args.channel,max_bytes=args.max_bytes,
                                  skip_bytes=args.skip_bytes,window_samples=args.window_samples)
        save_report(args.report,result)
        if args.plot: plot_windows(result,args.plot)
        print('Saved exploratory source report',args.report)
    elif args.command=='test-bits':
        save_report(args.report,binary_tests(args.file,max_bytes=args.max_bytes))
        print('Saved exploratory bit tests',args.report)
    elif args.command=='generate-file':
        generate_file(args.file,args.out,args.report,block_bytes=args.block_bytes,setup=args.setup)
        print('Saved unvalidated output',args.out)
    elif args.command=='generate-live':
        generate_live(args.out,args.report,seconds=args.seconds,rate=args.rate,freq=args.freq,
                      gain=args.gain,block_bytes=args.block_bytes,setup=args.setup)
        print('Saved unvalidated output',args.out)
    elif args.command=='stream':
        capture_stream(args.out,args.report,seconds=args.seconds,rate=args.rate,
                       freq=args.freq,gain=args.gain,setup=args.setup,chunk_bytes=args.chunk_bytes)
        print('Saved',args.out,args.report)
    elif args.command=='stream-file':
        if args.file.resolve() == args.out.resolve(): p.error('input and output must differ')
        with args.file.open('rb') as reader:
            process_stream(reader,args.out,args.report,total_bytes=args.file.stat().st_size,
                           chunk_bytes=args.chunk_bytes,setup=args.setup,
                           metadata={'source_file':str(args.file)})
        print('Saved',args.out,args.report)
    elif args.command=='capture':
        if not (0<args.seconds<=120): p.error('seconds must be in (0,120]')
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_bytes(acquire(args.seconds,args.rate,args.freq,args.gain))
        report=analyze_file(args.out)
        report.update({'setup':args.setup,'center_frequency_hz':args.freq,'sample_rate_sps':args.rate,'gain_db':args.gain,'duration_s':args.seconds})
        write_json(args.out.with_suffix('.json'),report)
        print('Saved',args.out)
    elif args.command=='analyze':
        report=analyze_file(args.file,args.max_lag,args.window_samples)
        report['setup']=args.setup
        output=args.report or args.file.with_suffix('.json')
        write_json(output,report)
        print('Saved',output)
    elif args.command=='health':
        report=health_file(args.file,args.window_bytes,args.repetition_cutoff,args.proportion_cutoff)
        output=args.report or args.file.with_suffix('.health.json')
        write_json(output,report)
        print('Saved',output)
    elif args.command=='compare':
        report=compare_files(args.first,args.second,args.max_lag,args.window_samples)
        write_json(args.report,report)
        print('Saved',args.report)
    elif args.command=='advanced':
        report=diagnose(args.file,args.rate,args.fft_size,args.max_pairs)
        write_json(args.report,report)
        if args.plot: plot_report(report,args.plot)
        print('Saved',args.report)
    elif args.command=='extract':
        report=condition_file(args.file,args.out,args.block_bytes)
        write_json(args.out.with_suffix(args.out.suffix+'.json'),report)
        print('Saved',args.out,'(EXPERIMENTAL; NOT for cryptography)')
if __name__=='__main__':main()
