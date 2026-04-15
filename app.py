import streamlit as st
import pandas as pd
import io

from utils import render_database_misure, verifica_stato_clienti, colora_clienti

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="RNA Business Intelligence", layout="wide")

st.title("📊 Analizzatore Registro Nazionale Aiuti")
st.markdown("Analisi strategica e qualificazione lead basata sui dati ufficiali RNA.")

# --- SIDEBAR ---
st.sidebar.header("Configurazione Confronto Personalizzato")

# Definiamo i nomi dei due gruppi da confrontare
label_set_a = st.sidebar.text_input("Nome Set A", value="FORMAZIONE", key="la")
kw_set_a = st.sidebar.text_input(f"Keyword per {label_set_a}", value="formazione, competenze, corso", key="ka")

st.sidebar.divider()

label_set_b = st.sidebar.text_input("Nome Set B", value="SABATINI", key="lb")
kw_set_b = st.sidebar.text_input(f"Keyword per {label_set_b}", value="formazione, competenze, corso", key="kb")

# TASTO DI AGGIORNAMENTO
btn_ricerca = st.sidebar.button("🔍 Aggiorna Analisi", use_container_width=True, type="primary")

st.sidebar.header("Ordinamento Report")
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
            return pd.read_csv(file, sep=';', encoding='utf-8-sig')

        df_raw = load_data(uploaded_file)

        # --- LOGICA DI CONFRONTO CLIENTI ---
        if uploaded_clienti is not None:
            # Chiamiamo la funzione che fa apparire il loading nella sidebar
            df_raw = verifica_stato_clienti(df_raw, uploaded_clienti)
        else:
            # Se non carichi il file, definiamo tutti come PROSPECT
            df_raw['STATO'] = "⚪ PROSPECT"
        
        # Pulizia Importi
        df_raw['RNA_IMPORTO'] = pd.to_numeric(df_raw['RNA_IMPORTO'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
        
        # Elaborazione parole chiave
        keywords = [k.strip().upper() for k in keywords_raw.split(',')]
        
        def is_target_row(row_text):
            text = str(row_text).upper()
            return any(k in text for k in keywords)

        # Identificazione righe target
        df_raw['is_target'] = df_raw['RNA_MISURA'].apply(is_target_row)
        df_raw['importo_target'] = df_raw.apply(lambda x: x['RNA_IMPORTO'] if x['is_target'] else 0, axis=1)

        # --- GENERAZIONE REPORT SINTETICO ---
        col_rna = ['RNA_PIVA', 'RNA_DATA', 'RNA_MISURA', 'RNA_IMPORTO', 'is_target', 'importo_target']
        col_ana = [c for c in df_raw.columns if c not in col_rna]
        
        report = df_raw.groupby('RAGIONE SOCIALE').agg({
            **{c: 'first' for c in col_ana if c != 'RAGIONE SOCIALE'},
            'RNA_MISURA': 'count',
            'RNA_IMPORTO': 'sum',
            'is_target': 'sum',
            'importo_target': 'sum'
        }).reset_index().rename(columns={
            'RNA_MISURA': 'N_TOT_AIUTI',
            'RNA_IMPORTO': 'VALORE_TOTALE_€',
            'is_target': 'N_AIUTI_TARGET',
            'importo_target': 'VALORE_TARGET_€'
        })

        # --- CALCOLO NUOVE COLONNE INCIDENZA ---
        report['INCIDENZA_N_TARGET_%'] = (report['N_AIUTI_TARGET'] / report['N_TOT_AIUTI'] * 100).fillna(0)
        report['INCIDENZA_VOL_TARGET_%'] = (report['VALORE_TARGET_€'] / report['VALORE_TOTALE_€'] * 100).fillna(0)
        report['RANK_INC_N'] = report['INCIDENZA_N_TARGET_%'].rank(ascending=False, method='min').astype(int)
        report['RANK_INC_VOL'] = report['INCIDENZA_VOL_TARGET_%'].rank(ascending=False, method='min').astype(int)

        # --- CALCOLO RANKING ---
        report['RANK_VOL_TOT'] = report['VALORE_TOTALE_€'].rank(ascending=False, method='min').astype(int)
        report['RANK_VOL_TARGET'] = report['VALORE_TARGET_€'].rank(ascending=False, method='min').astype(int)
        report['RANK_N_TOT'] = report['N_TOT_AIUTI'].rank(ascending=False, method='min').astype(int)
        report['RANK_N_TARGET'] = report['N_AIUTI_TARGET'].rank(ascending=False, method='min').astype(int)

        # Ordinamento
        report = report.sort_values(by=sort_options[sort_choice], ascending=False)

        st.divider()
        st.divider()
        render_database_misure(df_raw)
        
        st.divider()
        st.divider()
        st.subheader("📋 Report Riepilogativo della Ricerca Target")
        
        # --- KPI GENERALI ---
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Aziende Totali", len(report))
        k2.metric("Volume Totale Analizzato", f"€ {report['VALORE_TOTALE_€'].sum():,.0f}")
        k3.metric("Bandi Target Trovati", int(report['N_AIUTI_TARGET'].sum()))
        k4.metric("Volume Target Totale", f"€ {report['VALORE_TARGET_€'].sum():,.0f}")
        
        # --- REPORT GENERALE ---
        st.dataframe(
        report.style.apply(colora_clienti, axis=1),
        column_config={
            "STATO": st.column_config.TextColumn("Stato", width="medium"),
            "VALORE_TOTALE_€": st.column_config.NumberColumn("Budget Totale", format="%.2f €"),
            "VALORE_TARGET_€": st.column_config.NumberColumn("Budget Target", format="%.2f €"),
            "INCIDENZA_N_TARGET_%": st.column_config.NumberColumn("Incidenza N.", format="%.1f %%"),
            "INCIDENZA_VOL_TARGET_%": st.column_config.NumberColumn("Incidenza Vol.", format="%.1f %%"),
            },
            hide_index=True, 
            use_container_width=True
        )

        st.divider()

        # --- RICERCA AZIENDA E DETTAGLIO ---
        st.subheader("🎯 Analisi Dettagliata per Azienda")
        search_txt = st.text_input("Inserisci Ragione Sociale per visualizzare storia e ranking")

        if search_txt:
            azienda_details = df_raw[df_raw['RAGIONE SOCIALE'].str.contains(search_txt, case=False)].copy()
            
            if not azienda_details.empty:
                nome_esatto = azienda_details['RAGIONE SOCIALE'].iloc[0]
                info_rank = report[report['RAGIONE SOCIALE'] == nome_esatto].iloc[0]
                total_aziende = len(report)

                azienda_details['RNA_DATA_DT'] = pd.to_datetime(azienda_details['RNA_DATA'], dayfirst=True, errors='coerce')
                data_min = azienda_details['RNA_DATA_DT'].min()
                data_max = azienda_details['RNA_DATA_DT'].max()

                st.info(f"### 🏢 {nome_esatto}")
                
                # --- BLOCCO ETICHETTE (MANTENUTO ORIGINALE) ---
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("Periodo Analizzato", f"{data_min.year if pd.notnull(data_min) else 'N/D'} - {data_max.year if pd.notnull(data_max) else 'N/D'}")
                    # Metrica Incidenza Numero + Rank
                    st.metric("% Incidenza N. Target", f"{info_rank['INCIDENZA_N_TARGET_%']:.1f}%")
                    st.caption(f"🏆 Rank: **{info_rank['RANK_INC_N']}** su {len(report)}")
                    # Metrica Incidenza Volume + Rank
                    st.metric("% Incidenza Vol. Target", f"{info_rank['INCIDENZA_VOL_TARGET_%']:.1f}%")
                    st.caption(f"🏆 Rank: **{info_rank['RANK_INC_VOL']}**")
                with c2:
                    st.metric("Volume Totale (€)", f"{info_rank['VALORE_TOTALE_€']:,.2f} €")
                    st.caption(f"🏆 Rank: **{info_rank['RANK_VOL_TOT']}**")
                    st.metric("Volume Target (€)", f"{info_rank['VALORE_TARGET_€']:,.2f} €")
                    st.caption(f"🏆 Rank: **{info_rank['RANK_VOL_TARGET']}**")
                with c3:
                    st.metric("Bandi Totali", int(info_rank['N_TOT_AIUTI']))
                    st.caption(f"🏆 Rank: **{info_rank['RANK_N_TOT']}**")
                    st.metric("Bandi Target", int(info_rank['N_AIUTI_TARGET']))
                    st.caption(f"🏆 Rank: **{info_rank['RANK_N_TARGET']}**")

                st.write("---")
                def apply_highlight(row):
                    color = 'background-color: #d4edda' if row['is_target'] else ''
                    return [color] * len(row)

                cols_to_show = ['RAGIONE SOCIALE', 'RNA_DATA', 'RNA_MISURA', 'RNA_IMPORTO', 'is_target']
                st.dataframe(
                    azienda_details[cols_to_show].style.apply(apply_highlight, axis=1),
                    column_config={"is_target": None, "RNA_IMPORTO": st.column_config.NumberColumn(format="%.2f €")},
                    use_container_width=True, hide_index=True
                )
            else:
                st.warning("Nessuna azienda trovata.")

        st.divider()

        # --- SEZIONE GRAFICO SCATTER ---
        st.divider()
        st.subheader("📈 Analisi Correlazione: Budget Target vs Budget Totale")
        st.scatter_chart(
            report,
            y='VALORE_TOTALE_€',
            x='VALORE_TARGET_€',
            size='N_TOT_AIUTI',
            color='#2ecc71',
            use_container_width=True
        )

        csv_buffer = io.BytesIO()
        report.to_csv(csv_buffer, index=False, sep=';', encoding='utf-8-sig')
        st.sidebar.download_button("💾 Scarica Report (CSV)", csv_buffer.getvalue(), "Analisi_RNA.csv", "text/csv")

    except Exception as e:
        st.error(f"Errore: {e}")
else:
    st.info("👋 Carica il file CSV per iniziare.")
