import os
import requests
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title='PDNA Housing V5.3 | SVG', page_icon='🏠', layout='wide')
st.title('🏠 PDNA Housing V5.3 — Saint Vincent and the Grenadines')
st.caption('MULTIMODULE housing assessments · EC$ (XCD) · KoboToolbox live data')
DEFAULT_UID='aZJD8nNAfmc576q6HgK3VJ'

def setting(name, default=''):
    try: return st.secrets.get(name, os.environ.get(name, default))
    except Exception: return os.environ.get(name, default)

def field(record, *names):
    if not isinstance(record, dict): return None
    for name in names:
        if name in record and record[name] not in (None, ''): return record[name]
    for key, value in record.items():
        if key.split('/')[-1] in names and not isinstance(value, (list, dict)) and value not in (None, ''):
            return value
    return None

def numeric(value):
    try:
        result=float(value)
        return result if pd.notna(result) else 0.0
    except (ValueError, TypeError): return 0.0

def money(value): return f'EC$ {value:,.2f}'

@st.cache_data(ttl=300, show_spinner='Retrieving Housing V5 submissions…')
def fetch(server, uid, token):
    url=f"{server.rstrip('/')}/api/v2/assets/{uid}/data/?format=json&page_size=1000"
    headers={'Authorization': f'Token {token}'}
    result=[]
    while url:
        response=requests.get(url, headers=headers, timeout=45)
        response.raise_for_status()
        data=response.json()
        if isinstance(data, list): result.extend(data); break
        result.extend(data.get('results', []))
        url=data.get('next')
    return result

def find_modules(obj):
    found=[]
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, list) and key.split('/')[-1]=='housing_modules':
                found.extend(x for x in value if isinstance(x, dict))
            elif isinstance(value, dict): found.extend(find_modules(value))
    return found

def prepare(records):
    houses=[]; modules=[]
    for rec in records:
        rid=str(rec.get('_id', rec.get('__id', '')))
        damage=numeric(field(rec, 'summary_damage', 'direct_damage'))
        losses=numeric(field(rec, 'summary_losses', 'total_losses'))
        impact_raw=field(rec, 'summary_impact', 'total_impact')
        impact=numeric(impact_raw) if impact_raw is not None else damage+losses
        gps=field(rec, 'location_gps')
        lat=field(rec, '_location_gps_latitude', 'location_gps_latitude')
        lon=field(rec, '_location_gps_longitude', 'location_gps_longitude')
        if lat is None or lon is None:
            try:
                parts=str(gps).split();lat=float(parts[0]);lon=float(parts[1])
            except (ValueError, IndexError, TypeError): lat=lon=None
        houses.append({'Kobo ID':rid,'Housing address':str(field(rec,'housing_code','housing_address','Housing_address','address','housingaddress') or f'Property {rid}'),
                       'Assessment date':str(field(rec,'date','assessment_date') or rec.get('_submission_time',''))[:10],
                       'Damage':damage,'Losses':losses,'Impact':impact,
                       'Classification':str(field(rec,'summary_classification','clasification_damage') or 'Not specified'),
                       'Household goods':numeric(field(rec,'losses_household','household_goods','household_goods_lost')),
                       'Temporary rent':numeric(field(rec,'temporal_rent','temporary_rent')),
                       'Debris removal':numeric(field(rec,'debris_removal')),
                       'Other costs':numeric(field(rec,'other_costs')),
                       'Latitude':numeric(lat) if lat is not None else None,'Longitude':numeric(lon) if lon is not None else None})
        for i, module in enumerate(find_modules(rec), 1):
            modules.append({'Kobo ID':rid,'Module':int(numeric(field(module,'module_number')) or i),
                            'Construction type':str(field(module,'type_construction','construction_type','housing_type','type_of_construction') or 'Not specified'),
                            'Area (sq ft)':numeric(field(module,'building_area','module_area','area_sqf')),
                            'Replacement value':numeric(field(module,'replacement_value')),
                            'Structural damage':numeric(field(module,'module_direct_damage')),
                            'Classification':str(field(module,'module_classification_damage') or 'Not specified')})
    return pd.DataFrame(houses),pd.DataFrame(modules)

with st.sidebar:
    st.header('Data source')
    server=setting('KOBO_SERVER',setting('KOBO_BASE_URL','https://kf.kobotoolbox.org'))
    uid=setting('KOBO_ASSET_UID',DEFAULT_UID)
    token=setting('KOBO_API_TOKEN')
    st.caption('Kobo project UID')
    st.code(uid)
    if st.button('🔄 Refresh Kobo data'):
        fetch.clear();st.rerun()
    st.caption('Automatic cache expires after five minutes. API credentials remain in Streamlit Secrets.')
if not token:
    st.warning('Configure KOBO_API_TOKEN in Streamlit → App settings → Secrets.');st.stop()
try: records=fetch(server,uid,token)
except Exception as exc:
    st.error(f'Kobo API connection error: {exc}');st.stop()
houses,modules=prepare(records)
if houses.empty: st.info('No submitted housing assessments found in this project.');st.stop()

c1,c2,c3,c4=st.columns(4)
c1.metric('Housing assessments',f'{len(houses):,}')
c2.metric('Total damage',money(houses.Damage.sum()))
c3.metric('Total losses',money(houses.Losses.sum()))
c4.metric('Total impact',money(houses.Impact.sum()))
st.caption(f'Average damage per property: {money(houses.Damage.mean())}. Each property is counted once.')
errors=houses[(houses.Impact-houses.Damage-houses.Losses).abs()>0.02]
if not errors.empty:st.warning(f'{len(errors)} record(s) have Impact different from Damage + Losses. Please review their Kobo calculations.')

# Aggregate by construction typology using module-level structural damages only.
# Property totals remain authoritative for financial KPIs; do not add these again.
st.subheader('Structural damage by construction typology')
if not modules.empty:
    typology = (modules.groupby('Construction type', as_index=False)
                .agg(**{'Structural damage (EC$)': ('Structural damage', 'sum'),
                        'Modules': ('Module', 'size'),
                        'Properties': ('Kobo ID', 'nunique')}))
    typology = typology.sort_values('Structural damage (EC$)', ascending=True)
    typology_fig = px.bar(typology, x='Structural damage (EC$)', y='Construction type',
                          orientation='h', hover_data=['Modules', 'Properties'],
                          labels={'Construction type': 'Construction typology'})
    typology_fig.update_layout(yaxis={'categoryorder': 'array', 'categoryarray': typology['Construction type'].tolist()},
                               margin=dict(l=10, r=10, t=15, b=10))
    st.plotly_chart(typology_fig, use_container_width=True)
    st.caption(f'Typology chart uses {len(modules)} recorded construction module(s) from '
               f'{modules["Kobo ID"].nunique()} of {len(houses)} properties. '
               'It represents module structural damage only, not total property damage. '
               'Properties without module data are excluded from this chart.')
else:
    st.info('Construction typology chart unavailable: no module-level records were returned by Kobo.')

left, right = st.columns(2)
with left:
    st.subheader('Properties by damage classification')
    classification_order = ['No damage', 'Light', 'Mild', 'Severe', 'Destroyed', 'Not specified']
    counts = houses.groupby('Classification', as_index=False).size()
    counts['order'] = counts['Classification'].apply(lambda x: classification_order.index(x) if x in classification_order else len(classification_order))
    counts = counts.sort_values('order')
    class_fig = px.bar(counts, x='Classification', y='size',
                       labels={'size': 'Number of properties', 'Classification': 'Damage level'},
                       text='size')
    class_fig.update_layout(margin=dict(l=10, r=10, t=15, b=10))
    st.plotly_chart(class_fig, use_container_width=True)
    st.caption('Each property is counted once, using its overall Kobo classification.')
with right:
    st.subheader('Damage and losses composition')
    totals = pd.DataFrame({'Effect': ['Damage', 'Losses'],
                           'EC$': [houses.Damage.sum(), houses.Losses.sum()]})
    st.plotly_chart(px.pie(totals, names='Effect', values='EC$'), use_container_width=True)

st.subheader('Geographic distribution')
points=houses.dropna(subset=['Latitude','Longitude'])
points=points[points.Latitude.between(-90,90)&points.Longitude.between(-180,180)]
if not points.empty:
    st.map(points,latitude='Latitude',longitude='Longitude',size=100)
    st.caption('Locations reflect submitted GPS coordinates; test data may be outside Saint Vincent and the Grenadines.')
else: st.info('No valid GPS coordinates in current submissions.')

# Consolidate repeat-group construction details at property level only.
# Parent submission financial totals are authoritative and are never re-summed from modules.
summary = houses.drop(columns=['Latitude', 'Longitude', 'Property label'],errors='ignore').copy()
summary['Total area (sq ft)'] = pd.NA
summary['Replacement value (EC$)'] = pd.NA
summary['Structural damage (EC$)'] = pd.NA
if not modules.empty:
    aggregated = modules.groupby('Kobo ID', as_index=True).agg({
        'Area (sq ft)': 'sum',
        'Replacement value': 'sum',
        'Structural damage': 'sum',
    })
    summary['Total area (sq ft)'] = summary['Kobo ID'].map(aggregated['Area (sq ft)'])
    summary['Replacement value (EC$)'] = summary['Kobo ID'].map(aggregated['Replacement value'])
    summary['Structural damage (EC$)'] = summary['Kobo ID'].map(aggregated['Structural damage'])

st.subheader('Housing assessment records — consolidated by property')
st.caption('Each property appears once. Module areas, replacement values and structural damage are aggregated when module data exist. Blank module aggregates indicate unavailable module details, not zero. Property financial totals come directly from the parent Kobo assessment and are not recalculated from modules.')
columns = ['Kobo ID', 'Housing address', 'Assessment date', 'Total area (sq ft)',
           'Replacement value (EC$)', 'Structural damage (EC$)', 'Damage',
           'Losses', 'Impact', 'Classification', 'Household goods',
           'Temporary rent', 'Debris removal', 'Other costs']
st.dataframe(summary[columns], use_container_width=True, hide_index=True)
st.download_button('Download consolidated property assessments (CSV)',
                   summary[columns].to_csv(index=False).encode('utf-8-sig'),
                   'housing_v5_consolidated_properties.csv', 'text/csv')
st.caption('PDNA Housing Dashboard V5.3 · Typology and classification analysis · Direct KoboToolbox API · No separate Summary project required')
