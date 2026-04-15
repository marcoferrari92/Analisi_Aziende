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






def render_confronto_fondi(df_rna, label_a, kw_a_raw, label_b, kw_b_raw):
    """
    Esegue un confronto strategico tra due set di incentivi definiti dall'utente.
    Utile per identificare opportunità di Cross-Selling.
    """
    st.subheader(f"🔄 Analisi Incrociata: {label_a} vs {label_b}")
    st.markdown(f"""
    In questa sezione analizziamo come si distribuiscono gli aiuti tra **{label_a}** e **{label_b}**.
    L'obiettivo è individuare le aziende che hanno già investito in {label_a} ma non hanno ancora usufruito di {label_b}.
    """)

    # 1. Preparazione delle Regex per il filtraggio
    def clean_kw(raw):
        return '|'.join([k.strip().upper() for k in raw.split(',') if k.strip()])

    regex_a = clean_kw(kw_a_raw)
    regex_b = clean_kw(kw_b_raw)

    df_temp = df_rna.copy()
    
    # 2. Identificazione delle righe appartenenti ai due Set
    df_temp['is_a'] = df_temp['RNA_MISURA'].str.upper().str.contains(regex_a, na=False)
    df_temp['is_b'] = df_temp['RNA_MISURA'].str.upper().str.contains(regex_b, na=False)

    # 3. Aggregazione per Azienda
    # Calcoliamo se l'azienda ha almeno un bando del Set A e/o del Set B
    analisi = df_temp.groupby(['RAGIONE SOCIALE', 'STATO']).agg({
        'is_a': 'any',
        'is_b': 'any',
        'RNA_IMPORTO': 'sum'
    }).reset_index()

    # 4. Definizione dei Profili Strategici
    def definisci_profilo(row):
        if row['is_a'] and row['is_b']:
            return f"✅ Entrambi ({label_a} + {label_b})"
        if row['is_a']:
            return f"🚀 Solo {label_a} (Lead per {label_b})"
        if row['is_b']:
            return f"📚 Solo {label_b}"
        return "Altro"

    analisi['Profilo'] = analisi.apply(definisci_profilo, axis=1)
    
    # Filtriamo via le aziende che non appartengono a nessuno dei due set
    analisi_filtrata = analisi[analisi['Profilo'] != "Altro"].copy()

    if analisi_filtrata.empty:
        st.warning(f"Nessuna azienda trovata con i parametri inseriti per {label_a} o {label_b}.")
        return

    # 5. Visualizzazione Grafica (Plotly)
    st.write("#### Distribuzione dei segmenti")
    conteggi = analisi_filtrata['Profilo'].value_counts().reset_index()
    conteggi.columns = ['Profilo', 'Numero_Aziende']

    fig = px.bar(
        conteggi, 
        x='Profilo', 
        y='Numero_Aziende',
        color='Profilo',
        text_auto=True,
        title=f"Segmentazione Aziende: {label_a} e {label_b}",
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    st.plotly_chart(fig, use_container_width=True)

    # 6. Tabella Opportunità (Lead Generation)
    st.write(f"#### 🎯 Opportunità Prioritarie: Solo {label_a}")
    st.info(f"Queste aziende hanno ottenuto {label_a} ma non risultano aver beneficiato di {label_b}.")
    
    lead_list = analisi_filtrata[
        (analisi_filtrata['is_a'] == True) & 
        (analisi_filtrata['is_b'] == False)
    ].sort_values(by='RNA_IMPORTO', ascending=False)

    st.dataframe(
        lead_list[['RAGIONE SOCIALE', 'STATO', 'RNA_IMPORTO']],
        column_config={
            "RNA_IMPORTO": st.column_config.NumberColumn("Budget Totale Aiuti (€)", format="%.2f €"),
            "STATO": "Qualifica"
        },
        use_container_width=True,
        hide_index=True
    )

    # 7. Download dei Lead
    csv_buffer = io.BytesIO()
    lead_list.to_csv(csv_buffer, index=False, sep=';', encoding='utf-8-sig')
    st.download_button(
        label=f"📩 Scarica Lead {label_a} -> {label_b}",
        data=csv_buffer.getvalue(),
        file_name=f"Lead_{label_a}_vs_{label_b}.csv",
        mime="text/csv"
    )


