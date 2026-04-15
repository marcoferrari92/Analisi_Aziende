import streamlit as st
import pandas as pd
import io

# Importiamo le funzioni dal tuo file esterno utils.py
from utils import render_database_misure, verifica_stato_clienti, colora_clienti, render_confronto_fondi, render_statistiche_budget

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="RNA Business Intelligence", layout="wide")

st.title("📊 Analizzatore Registro Nazionale Aiuti")
st.markdown("Analisi strategica e qualificazione lead basata sui dati ufficiali RNA.")

# --- FUNZIONE DI NORMALIZZAZIONE E PULIZIA ---
def preprocess_dataframe(df):
    """
    Rileva le colonne fondamentali indipendentemente dal case (Maiuscole/Minuscole)
    e rimuove quelle indesiderate.
    """
    # Mappa delle colonne che vogliamo "fissare"
    mappa_standard = {
        'RAGIONE SOCIALE': 'RAGIONE SOCIALE',
        'CITTÀ': 'CITTÀ',
        'CITTA': 'CITTÀ',
        'CLASSIFICAZIONE': 'CLASSIFICAZIONE',
        'N. DIPE': 'N. Dipe',
        'CODICE ATECO': 'Codice ateco'
    }
    
    rename_dict = {}
    cols_to_drop = []

    for col in df.columns:
        col_clean = col.strip().upper()
        
        # 1. Identifichiamo colonne da ignorare o eliminare
        if col_clean in ['RAGIONE SOCIALE EXT', 'N. DIPE CALC']:
            cols_to_drop.append(col)
            continue
            
        # 2. Mappiamo le colonne necessarie al formato standard dello script
        if col_clean in mappa_standard:
            rename_dict[col] = mappa_standard[col_clean]

    # Eseguiamo pulizia e rinomina
    df = df.drop(columns=cols_to_drop, errors='ignore')
    df = df.rename(columns=rename_dict)
    
    # 3. Gestione duplicati per evitare crash nel set_index/groupby
    if 'RAGIONE SOCIALE' in df.columns:
        df['RAGIONE SOCIALE'] = df['RAGIONE SOCIALE'].astype(str).str.strip()
        df = df.drop_duplicates(subset=['RAGIONE SOCIALE'], keep='first')
        
    return df

# --- SIDEBAR ---
st.sidebar.header("1. Caricamento Dati")
uploaded_file = st.sidebar.file_uploader("Carica file RNA", type=["csv"])
uploaded_clienti = st.sidebar.file_uploader("Carica Database Clienti (Opzionale)", type=["csv"])

st.sidebar.divider()

st.sidebar.header("2. Configurazione Confronto Strategico")
label_set_a = st.sidebar.text_input("Nome Set A", value="FORMAZIONE", key="la")
kw_set_a = st.sidebar.text_area(f"Keyword per {label_set_a}", value="formazione, competenze, corso", key="ka")

st.sidebar.divider()

label_set_b = st.sidebar.text_input("Nome Set B", value="SABATINI", key="lb")
kw_set_b = st.sidebar.text_area(f"Keyword per {label_set_b}", value="sabatini", key="kb")

st.sidebar.header("3. Ordinamento Report")
sort_options = {
    "Numero Aiuti Target": "N_AIUTI_TARGET",
    "Valore Aiuti Target (€)": "VALORE_TARGET_€",
    "Incidenza Numero (%)": "INCIDENZA_N_TARGET_%",
    "Incidenza Volume (%)": "INCIDENZA_VOL_TARGET_%",
    "Valore Totale (€)": "VALORE_TOTALE_€",
    "Numero Totale Aiuti": "N_TOT_AIUTI"
}
sort_choice = st.sidebar.selectbox("Ordina tabella per:", list(sort_options.keys()), index=0)

# --- LOGICA DI ELABORAZIONE ---
if uploaded_file is not None:
    try:
        @st.cache_data
        def load_data(file):
            # sep=None con engine='python' indovina se il separatore è , o ;
            df = pd.read_csv(file, sep=None, engine='python', encoding='utf-8-sig')
            df = preprocess_dataframe(df)
            return df

        df_raw = load_data(uploaded_file)

        # Controllo di sicurezza
        if 'RAGIONE SOCIALE' not in df_raw.columns:
            st.error("❌ Impossibile trovare la colonna 'Ragione Sociale'. Controlla il file.")
            st.stop()

        # --- LOGICA DI CONFRONTO CLIENTI ---
        if uploaded_clienti is not None:
            df_raw = verifica_stato_clienti(df_raw, uploaded_clienti)
        else:
            df_raw['STATO'] = "⚪ PROSPECT"
        
        # Pulizia Importi
        df_raw['RNA_IMPORTO'] = pd.to_numeric(df_raw['RNA_IMPORTO'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
        
        # --- FILTRO TARGET ---
        keywords_target = [k.strip().upper() for k in kw_set_a.split(',')]
        
        def is_target_row(row_text):
            text = str(row_text).upper()
            return any(k in text for k in keywords_target)

        df_raw['is_target'] = df_raw['RNA_MISURA'].apply(is_target_row)
        df_raw['importo_target'] = df_raw.apply(lambda x: x['RNA_IMPORTO'] if x['is_target'] else 0, axis=1)

        # --- GENERAZIONE REPORT SINTETICO DINAMICO ---
        agg_dict = {
            'RNA_MISURA': 'count',
            'RNA_IMPORTO': 'sum',
            'is_target': 'sum',
            'importo_target': 'sum',
            'STATO': 'first'
        }
        
        # Aggiungiamo colonne opzionali solo se esistono nel file dopo il preprocessing
        for col_opt in ['CITTÀ', 'CLASSIFICAZIONE', 'N. Dipe', 'Codice ateco']:
            if col_opt in df_raw.columns:
                agg_dict[col_opt] = 'first'

        report = df_raw.groupby('RAGIONE SOCIALE').agg(agg_dict).reset_index().rename(columns={
            'RNA_MISURA': 'N_TOT_AIUTI',
            'RNA_IMPORTO': 'VALORE_TOTALE_€',
            'is_target': 'N_AIUTI_TARGET',
            'importo_target': 'VALORE_TARGET_€'
        })

        # --- CALCOLI INCIDENZA E RANKING ---
        report['INCIDENZA_N_TARGET_%'] = (report['N_AIUTI_TARGET'] / report['N_TOT_AIUTI'] * 100).fillna(0)
        report['INCIDENZA_VOL_TARGET_%'] = (report['VALORE_TARGET_€'] / report['VALORE_TOTALE_€'] * 100).fillna(0)
        
        for col, new_col in [('VALORE_TOTALE_€', 'RANK_VOL_TOT'), ('VALORE_TARGET_€', 'RANK_VOL_TARGET'), 
                             ('N_TOT_AIUTI', 'RANK_N_TOT'), ('N_AIUTI_TARGET', 'RANK_N_TARGET'),
                             ('INCIDENZA_N_TARGET_%', 'RANK_INC_N'), ('INCIDENZA_VOL_TARGET_%', 'RANK_INC_VOL')]:
            report[new_col] = report[col].rank(ascending=False, method='min').astype(int)

        report = report.sort_values(by=sort_options[sort_choice], ascending=False)

        # --- VISUALIZZAZIONE ---
        render_database_misure(df_raw)
        
        st.divider()
        with st.expander(f"🎯 Strategia Commerciale: {label_set_a} vs {label_set_b}", expanded=True):
            render_confronto_fondi(df_raw, label_set_a, kw_set_a, label_set_b, kw_set_b)

        st.divider()
        st.subheader(f"📋 Analisi Target: Focus su {label_set_a}")
        
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Aziende Totali", len(report))
        k2.metric("Volume Totale", f"€ {report['VALORE_TOTALE_€'].sum():,.0f}")
        k3.metric(f"Bandi {label_set_a}", int(report['N_AIUTI_TARGET'].sum()))
        k4.metric(f"Valore {label_set_a}", f"€ {report['VALORE_TARGET_€'].sum():,.0f}")
        
        st.dataframe(
            report.style.apply(colora_clienti, axis=1),
            column_config={
                "VALORE_TOTALE_€": st.column_config.NumberColumn(format="%.2f €"),
                "VALORE_TARGET_€": st.column_config.NumberColumn(format="%.2f €"),
                "INCIDENZA_N_TARGET_%": st.column_config.NumberColumn(format="%.1f %%"),
                "INCIDENZA_VOL_TARGET_%": st.column_config.NumberColumn(format="%.1f %%"),
            },
            hide_index=True, use_container_width=True
        )

        with st.expander(f"📊 Analisi Economica e Distribuzione {label_set_a}", expanded=True):
            render_statistiche_budget(df_raw, label_set_a, kw_set_a)

        st.divider()
        st.subheader("🔍 Ricerca Dettagliata Azienda")
        search_txt = st.text_input("Inserisci Ragione Sociale")

        if search_txt:
            azienda_details = df_raw[df_raw['RAGIONE SOCIALE'].str.contains(search_txt, case=False)].copy()
            if not azienda_details.empty:
                nome_esatto = azienda_details['RAGIONE SOCIALE'].iloc[0]
                info_rank = report[report['RAGIONE SOCIALE'] == nome_esatto].iloc[0]
                
                st.info(f"### 🏢 {nome_esatto} ({info_rank['STATO']})")
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("% Incidenza N.", f"{info_rank['INCIDENZA_N_TARGET_%']:.1f}%")
                    st.caption(f"🏆 Rank: **{info_rank['RANK_INC_N']}**")
                with c2:
                    st.metric("Volume Totale", f"{info_rank['VALORE_TOTALE_€']:,.2f} €")
                    st.caption(f"🏆 Rank: **{info_rank['RANK_VOL_TOT']}**")
                with c3:
                    st.metric("Bandi Totali", int(info_rank['N_TOT_AIUTI']))
                    st.caption(f"🏆 Rank: **{info_rank['RANK_N_TOT']}**")

                st.dataframe(azienda_details[['RNA_DATA', 'RNA_MISURA', 'RNA_IMPORTO', 'is_target']], use_container_width=True)

        st.sidebar.download_button("💾 Scarica Report Completo", report.to_csv(index=False, sep=';', encoding='utf-8-sig'), "Analisi_RNA.csv")

    except Exception as e:
        st.error(f"Errore: {e}")
else:
    st.info("👋 Carica il file RNA per iniziare.")
