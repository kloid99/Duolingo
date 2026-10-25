from pathlib import Path
import sys,os,json,hashlib
ROOT=Path(__file__).resolve().parent
sys.path.append(str(ROOT.parent/'cohort_v1'/'tmp'/'python_deps'))
os.environ['MPLCONFIGDIR']=str(ROOT/'tmp'/'mplconfig')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager,ticker
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import pandas as pd

OUT=ROOT/'figures';OUT.mkdir(exist_ok=True)
font_manager.fontManager.addfont('C:/Windows/Fonts/malgun.ttf')
plt.rcParams.update({'font.family':'Malgun Gothic','font.size':11,'axes.unicode_minus':False,
    'figure.facecolor':'white','text.color':'#24364B','axes.labelcolor':'#24364B',
    'xtick.color':'#526175','ytick.color':'#24364B','svg.fonttype':'none'})
r=json.loads((ROOT/'results_retention.json').read_text(encoding='utf-8'))
s=pd.DataFrame(r['segment_summary']).set_index('segment');order=list(s.index)
d=pd.read_csv(ROOT/'segment_daily_retention.csv')
c=pd.read_csv(ROOT/'first_return_cohorts.csv');states=pd.read_csv(ROOT/'segment_followup_states.csv')
for name in ['segment_daily_retention.csv','first_return_cohorts.csv','segment_followup_states.csv']:
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==r['outputs'][name]['sha256']
scope='정여진 세그먼트 고정: 3/1~7  |  추적: 2013.03.08~11  |  UTC · 사용자 기준'
blue=LinearSegmentedColormap.from_list('learning',['#F2F6FA','#9EBFDB','#234C76'])

def save(fig,name):
    fig.savefig(OUT/(name+'.png'),dpi=220)
    fig.savefig(OUT/(name+'.svg'))
    plt.close(fig)

fig,axes=plt.subplots(1,2,figsize=(16,7.4));fig.subplots_adjust(left=.19,right=.96,bottom=.20,top=.77,wspace=.13)
fig.text(.03,.95,'다시 학습하는 것과 반복해서 학습하는 것을 구분한다',fontsize=19,fontweight='bold')
fig.text(.03,.90,scope,fontsize=11,color='#526175')
for panel,(key,title) in enumerate([('daily_relearning_rate','① 해당 날짜 학습률'),('cumulative_repeat_rate','② 해당 날짜까지 2일 이상 학습률')]):
    ax=axes[panel]
    mat=d.pivot(index='segment',columns='date',values=key).reindex(order).to_numpy()
    im=ax.imshow(mat,cmap=blue,vmin=0,vmax=.6,aspect='auto')
    ax.set_title(title,fontsize=12,pad=17)
    ax.set_xticks(range(4),['3/8','3/9','3/10','3/11']);ax.xaxis.tick_top()
    ax.set_yticks(range(len(order)),[f'{x} (n={int(s.loc[x,"cohort_users"]):,})' for x in order] if panel==0 else [])
    ax.tick_params(length=0,pad=8)
    for i in range(len(order)):
        for j in range(4):ax.text(j,i,f'{mat[i,j]:.1%}',ha='center',va='center',fontsize=12,color='white' if mat[i,j]>=.34 else '#24364B')
    ax.set_xticks(np.arange(-.5,4,1),minor=True);ax.set_yticks(np.arange(-.5,len(order),1),minor=True)
    ax.grid(which='minor',color='white',linewidth=2);ax.tick_params(which='minor',length=0)
    for sp in ax.spines.values():sp.set_visible(False)
fig.text(.03,.12,'두 지표 모두 분모는 처음 확정한 세그먼트 전체 사용자입니다. 비활동 사용자도 포함합니다.',fontsize=11,color='#526175')
fig.text(.03,.07,'②는 서로 다른 날짜에 2일 이상 학습한 비율입니다. 3/8에는 추적 첫날이므로 모든 집단이 0%입니다.',fontsize=11,color='#526175')
fig.text(.03,.025,'색 척도: 0~60%, 두 패널에 공통 적용. 날짜별 활동률은 단조 감소하는 생존율이 아닙니다.',fontsize=10,color='#526175')
save(fig,'01_시점별_재학습과_반복학습')

allc=c[c.segment=='전체'].sort_values('first_return_date')
mat=allc[[f'D{k}_relearning_rate' for k in range(4)]].to_numpy()
fig,ax=plt.subplots(figsize=(12.5,6.6));fig.subplots_adjust(left=.27,right=.89,top=.73,bottom=.23)
fig.text(.04,.94,'복귀 후에도 학습을 이어가는가?',fontsize=20,fontweight='bold')
fig.text(.04,.88,'행: 이후 관측기간의 첫 재학습일  |  열: 복귀일 D0부터의 경과일  |  전체 세그먼트 합산',fontsize=10.5,color='#526175')
cm=LinearSegmentedColormap.from_list('cohort',['#F2F6FA','#89AFCE','#234C76']);cm.set_bad('#EEF0F2')
im=ax.imshow(np.ma.masked_invalid(mat),cmap=cm,vmin=0,vmax=1,aspect='auto')
ax.set_xticks(range(4),['D0 · 복귀일','D+1','D+2','D+3']);ax.xaxis.tick_top()
ax.set_yticks(range(4),[f'{row.first_return_date[5:].replace("-","/")} (n={int(row.return_cohort_users):,})' for row in allc.itertuples()])
ax.tick_params(length=0,pad=10)
for i in range(4):
    for j in range(4):ax.text(j,i,'관측 불가' if np.isnan(mat[i,j]) else f'{mat[i,j]:.1%}',ha='center',va='center',fontsize=12,color='white' if not np.isnan(mat[i,j]) and mat[i,j]>.6 else '#24364B')
ax.set_xticks(np.arange(-.5,4,1),minor=True);ax.set_yticks(np.arange(-.5,4,1),minor=True)
ax.grid(which='minor',color='white',linewidth=3);ax.tick_params(which='minor',length=0)
for sp in ax.spines.values():sp.set_visible(False)
cb=fig.colorbar(im,ax=ax,fraction=.032,pad=.035,ticks=[0,.5,1]);cb.ax.yaxis.set_major_formatter(ticker.PercentFormatter(1,decimals=0));cb.outline.set_visible(False)
fig.text(.04,.145,'분모: 각 날짜에 처음 재학습한 사용자 수. D0는 집단 정의에 따라 100%입니다.',fontsize=10.5,color='#526175')
fig.text(.04,.095,'추적 종료는 3/11입니다. 뒤쪽 코호트의 미관측 구간은 0%로 처리하지 않습니다.',fontsize=10.5,color='#526175')
fig.text(.04,.045,'복귀자 중 반복 학습을 보는 조건부 코호트입니다. 전체 사용자 중 재학습률과 분모가 다릅니다.',fontsize=10.5,color='#526175')
save(fig,'02_복귀일_기준_재학습_코호트')

names=r['states'];colors=['#E7EBEF','#CB8B54','#9EB9D1','#285780']
rank=s.sort_values('repeat_4day_rate',ascending=False).index.tolist()
p=states.pivot(index='segment',columns='state',values='share').reindex(index=rank,columns=names)
fig,ax=plt.subplots(figsize=(14,7.7));fig.subplots_adjust(left=.27,right=.96,top=.72,bottom=.23)
fig.text(.035,.94,'복귀에 그친 사용자와 반복 학습자를 구분한다',fontsize=19,fontweight='bold')
fig.text(.035,.885,scope,fontsize=10.5,color='#526175')
y=np.arange(len(rank));left=np.zeros(len(rank))
for name,color in zip(names,colors):
    values=p[name].to_numpy();ax.barh(y,values,left=left,color=color,height=.65,label=name)
    for i,v in enumerate(values):
        if v>=.045:ax.text(left[i]+v/2,i,f'{v:.1%}',ha='center',va='center',fontsize=10,color='white' if name==names[3] else '#24364B')
    left+=values
ax.set_yticks(y,[f'{x} (n={int(s.loc[x,"cohort_users"]):,})' for x in rank]);ax.invert_yaxis()
ax.set_xlim(0,1);ax.xaxis.set_major_formatter(ticker.PercentFormatter(1,decimals=0));ax.xaxis.set_major_locator(ticker.MultipleLocator(.2))
ax.tick_params(length=0,pad=8)
for sp in ax.spines.values():sp.set_visible(False)
ax.legend(loc='lower left',bbox_to_anchor=(-.3,1.05),ncols=2,frameon=False,fontsize=10)
fig.text(.035,.15,'4일 중 2일 이상 재학습한 비율은 꾸준형 55.9%, 습관 형성형 24.4%, 멈춤-꾸준형 22.3%입니다.',fontsize=11,color='#24364B')
fig.text(.035,.10,'3일 비활동은 3/8에 한 번 재학습한 뒤 3/9~11에 기록이 없는 경우입니다. 장기 이탈 확정은 아닙니다.',fontsize=10.5,color='#526175')
fig.text(.035,.05,'1회 재학습·추적 종료에는 늦게 복귀해 추가 학습을 관찰할 시간이 짧은 사용자도 포함됩니다.',fontsize=10.5,color='#526175')
save(fig,'03_세그먼트별_반복학습과_비활동양상')

daily=pd.DataFrame(r['overall_daily'])
fig,ax=plt.subplots(figsize=(12.5,6.2));fig.subplots_adjust(left=.11,right=.96,top=.76,bottom=.24)
fig.text(.035,.94,'재학습 증가와 비활동 신호를 함께 추적한다',fontsize=19,fontweight='bold')
fig.text(.035,.88,'전체 기준집단 82,467명  |  3일 이상 연속 비활동: 마지막 학습일 이후 달력 날짜 기준',fontsize=10.5,color='#526175')
x=np.arange(4)
for col,label,color in [('cumulative_return_rate','누적 1회 이상 재학습','#567A9C'),('cumulative_repeat_rate','누적 2일 이상 재학습','#285780'),('inactive_3day_rate','해당 시점 3일 이상 비활동','#BA7F4D')]:
    y=daily[col].to_numpy();ax.plot(x,y,marker='o',color=color,label=label,linewidth=2)
    for i,v in enumerate(y):ax.annotate(f'{v:.1%}',(i,v),xytext=(0,9),textcoords='offset points',ha='center',fontsize=10,color=color)
ax.set_xticks(x,['3/8','3/9','3/10','3/11']);ax.set_ylim(-.025,1)
ax.yaxis.set_major_formatter(ticker.PercentFormatter(1,decimals=0));ax.yaxis.set_major_locator(ticker.MultipleLocator(.2));ax.grid(axis='y',color='#E4EAF0',linewidth=.8)
ax.legend(loc='lower left',bbox_to_anchor=(0,1.02),ncols=3,frameon=False,fontsize=10)
for sp in ax.spines.values():sp.set_visible(False)
fig.text(.035,.13,'누적 재학습과 현재 비활동은 겹칠 수 있습니다. 한 번 복귀한 뒤 다시 쉬는 사용자도 있기 때문입니다.',fontsize=10.5,color='#526175')
fig.text(.035,.075,'비활동에는 기준일 이전부터 쉬던 사용자도 포함됩니다. 증가분 전체를 신규 이탈로 해석하지 않습니다.',fontsize=10.5,color='#526175')
fig.text(.035,.025,'3일 기준은 운영상 가정이며, 2일 기준 결과도 분석표에 함께 제공합니다.',fontsize=10,color='#526175')
save(fig,'04_시점별_재학습과_비활동신호')
print('Created',len(list(OUT.glob('*.png'))),'PNG figures and matching SVGs')
