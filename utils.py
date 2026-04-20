import pandas as pd
import streamlit as st
import io
import plotly.express as px

def render_database_misure(df_rna):
    """
    Crea il database univoco degli aiuti con analisi grafica Plotly.
    """
    st.subheader("📋 Database degli Aiuti")
    st.markdown("""
    Questa sezione raggruppa tutti i bandi trovati nel file RNA, indicando quante aziende li hanno utilizzati 
    e il volume economico totale per ogni singolo aiuto.
    """)

    # 1. Elaborazione dati
    df_temp = df_rna.copy()
    df_temp['importo_numerico'] = pd.to_numeric(
        df_temp['RNA_IMPORTO'].astype(str).str.replace(',', '.'), 
        errors='coerce'
    ).fillna(0)

    db_misure = df_temp.groupby('RNA_MISURA').agg({
        'RAGIONE SOCIALE': 'nunique',
        'RNA_MISURA': 'count',
        'importo_numerico': 'sum'
    }).rename(columns={
        'RAGIONE SOCIALE': 'Aziende_Coinvolte',
        'RNA_MISURA': 'Numero_Erogazioni',
        'importo_numerico': 'Valore_Totale_€'
    }).reset_index()

    db_misure = db_misure.sort_values(by='Numero_Erogazioni', ascending=False)

    # 2. Visualizzazione Statistiche
    m1, m2 = st.columns(2)
    m1.metric("Misure Univoche Trovate", len(db_misure))
    m2.metric("Volume Economico Totale", f"€ {db_misure['Valore_Totale_€'].sum():,.0f}")

    # 3. Grafici Interattivi
    st.write("### 📊 Analisi Visuale del Mercato")
    tab1, tab2, tab3 = st.tabs(["💰 Top per Budget", "🎯 Diffusione Misure", "📈 Matrice Opportunità"])

    with tab1:
        top_valore = db_misure.sort_values(by='Valore_Totale_€', ascending=False).head(10)
        fig_val = px.bar(
            top_valore, 
            x='Valore_Totale_€', 
            y='RNA_MISURA', 
            orientation='h',
            title="Top 10 Bandi per Volume Economico (€)",
            color='Valore_Totale_€',
            color_continuous_scale='Viridis'
        )
        fig_val.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_val, use_container_width=True)

    with tab2:
        fig_tree = px.treemap(
            db_misure.head(20), 
            path=['RNA_MISURA'], 
            values='Numero_Erogazioni',
            title="Prime 20 Misure per Diffusione (N. Erogazioni)",
            color='Numero_Erogazioni',
            color_continuous_scale='Blues'
        )
        st.plotly_chart(fig_tree, use_container_width=True)

    with tab3:
        fig_scatter = px.scatter(
            db_misure, 
            x='Aziende_Coinvolte', 
            y='Valore_Totale_€',
            size='Numero_Erogazioni',
            hover_name='RNA_MISURA',
            title="Relazione Aziende vs Budget (Scala Log)",
            color='Valore_Totale_€',
            log_y=True
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    # 4. Tabella Dati
    st.write("### 🗄️ Dati Analitici")
    st.dataframe(
        db_misure,
        column_config={
            "Valore_Totale_€": st.column_config.NumberColumn(format="%.2f €"),
        },
        hide_index=True,
        use_container_width=True
    )

    # 5. Download
    csv_misure = io.BytesIO()
    db_misure.to_csv(csv_misure, index=False, sep=';', encoding='utf-8-sig')
    st.download_button("💾 Scarica Database Misure (CSV)", csv_misure.getvalue(), "Database_Misure_RNA.csv", "text/csv")


def verifica_stato_clienti(df_rna, uploaded_clienti):
    """
    Confronta il database RNA con il file Clienti tramite Partita IVA.
    Ritorna il dataframe RNA arricchito con la colonna 'STATO'.
    """
    try:
        # 1. Caricamento del file Clienti 2026 (separatore ;)
        # Usiamo 'low_memory=False' per gestire colonne con tipi misti
        df_clienti = pd.read_csv(uploaded_clienti, sep=';', encoding='utf-8-sig', low_memory=False)
        
        if 'Partita IVA' not in df_clienti.columns:
            st.error("⚠️ Errore: Colonna 'Partita IVA' non trovata nel file clienti!")
            return df_rna

        # 2. Pulizia e Normalizzazione P.IVA Clienti
        # Rimuoviamo spazi, rendiamo tutto stringa e togliamo eventuali prefissi
        lista_piva_clienti = (
            df_clienti['Partita IVA']
            .astype(str)
            .str.strip()
            .str.replace(' ', '')
            .unique()
            .tolist()
        )

        # 3. Pulizia P.IVA nel database RNA
        # Creiamo una versione pulita per il confronto
        df_rna['RNA_PIVA_CLEAN'] = (
            df_rna['RNA_PIVA']
            .astype(str)
            .str.strip()
            .str.replace(' ', '')
        )

        # 4. Matching (Il confronto vero e proprio)
        # Se la P.IVA pulita è nella lista clienti -> CLIENTE, altrimenti PROSPECT
        df_rna['STATO'] = df_rna['RNA_PIVA_CLEAN'].apply(
            lambda x: "🟢 CLIENTE" if x in lista_piva_clienti else "⚪ PROSPECT"
        )
        
        # Rimuoviamo la colonna di servizio per pulizia
        df_rna = df_rna.drop(columns=['RNA_PIVA_CLEAN'])
        
        st.sidebar.success(f"✅ Confronto completato: {len(lista_piva_clienti)} clienti caricati.")
        return df_rna

    except Exception as e:
        st.error(f"❌ Errore durante il confronto P.IVA: {e}")
        return df_rna


def colora_clienti(row):
    # Definiamo il colore: verde chiaro per i clienti
    # Il codice HEX #d4edda è il classico verde "success"
    color = 'background-color: #d4edda' if "CLIENTE" in str(row['STATO']) else ''
    return [color] * len(row)




def render_statistiche_budget(df_rna, label_a, kw_a_raw):
    st.subheader(f"📊 Statistiche Budget: {label_a}")
    
    # 1. Preparazione dati e Regex
    def clean_kw(raw):
        return '|'.join([k.strip().upper() for k in raw.split(',') if k.strip()])

    regex_a = clean_kw(kw_a_raw)
    df_temp = df_rna.copy()
    
    # 2. Calcolo importi per riga
    df_temp['is_a'] = df_temp['RNA_MISURA'].str.upper().str.contains(regex_a, na=False)
    df_temp['importo_a'] = df_temp.apply(lambda x: x['RNA_IMPORTO'] if x['is_a'] else 0, axis=1)

    # 3. Aggregazione per Azienda
    stats_aziende = df_temp.groupby('RAGIONE SOCIALE').agg({
        'RNA_IMPORTO': 'sum',
        'importo_a': 'sum'
    }).reset_index()
    
    # Filtriamo le aziende che hanno ricevuto almeno un bando del Set A
    target_aziende = stats_aziende[stats_aziende['importo_a'] > 0].copy()
    
    if target_aziende.empty:
        st.warning(f"Dati insufficienti per calcolare statistiche su {label_a}.")
        return

    # Calcolo Incidenza %
    target_aziende['incidenza_%'] = (target_aziende['importo_a'] / target_aziende['RNA_IMPORTO']) * 100

    # 4. Calcolo KPI
    media_abs = target_aziende['importo_a'].mean()
    mediana_abs = target_aziende['importo_a'].median()
    media_perc = target_aziende['incidenza_%'].mean()
    mediana_perc = target_aziende['incidenza_%'].median()

    # 5. Visualizzazione Metriche
    st.write(f"Analisi basata su **{len(target_aziende)}** aziende che hanno ricevuto {label_a}:")
    
    c1, c2 = st.columns(2)
    with c1:
        st.metric(f"Media Budget {label_a}", f"€ {media_abs:,.2f}")
        st.metric(f"Incidenza Media %", f"{media_perc:.1f}%")
        st.caption("La media risente dei grandi importi.")
        
    with c2:
        st.metric(f"Mediana Budget {label_a}", f"€ {mediana_abs:,.2f}")
        st.metric(f"Incidenza Mediana %", f"{mediana_perc:.1f}%")
        st.caption("La mediana indica il valore centrale (più realistico).")

    # 6. Grafico Distribuzione (opzionale ma utile)
    fig_dist = px.histogram(
        target_aziende, 
        x='importo_a', 
        nbins=30,
        title=f"Distribuzione Budget {label_a}",
        labels={'importo_a': 'Budget Erogato (€)'},
        color_discrete_sequence=['#2ecc71']
    )
    st.plotly_chart(fig_dist, use_container_width=True)
