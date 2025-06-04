import streamlit as st
import pandas as pd
import io
import gzip
import math

def archive_uploader():
    return st.file_uploader("**Selecione o arquivo VCF ou VCF.GZ**", type=["vcf", "vcf.gz"])

def parse_vcf(file):
    if file.name.endswith(".vcf.gz"):
        with gzip.open(file, 'rt') as f:
            lines = f.read().splitlines()
    else:
        lines = file.read().decode("utf-8").splitlines()

    header_lines = [line for line in lines if line.startswith("##")]
    column_line = next(line for line in lines if line.startswith("#CHROM"))
    data_lines = [line for line in lines if not line.startswith("#")]

    columns = column_line.lstrip("#").split("\t")
    df = pd.DataFrame([line.split("\t") for line in data_lines], columns=columns)

    return df, header_lines, column_line

def edit_sample_genotypes(df, sample_name):
    st.write(f"### Editar genótipos da amostra: `{sample_name}`")

    col_main, col_filters = st.columns([3, 1])

    with col_filters:
        chroms = sorted(df["CHROM"].unique())
        selected_chrom = st.selectbox("**Cromossomo**", chroms)
        pos_filter = st.text_input("**Posição** (ex: 1234567 ou 1230000-1240000)", "")
        per_page = st.slider("Itens por página", 1, 50, 10)

    filtered_df = df[df["CHROM"] == selected_chrom]

    if pos_filter:
        try:
            if "-" in pos_filter:
                start, end = map(int, pos_filter.split("-"))
                filtered_df = filtered_df[
                    (filtered_df["POS"].astype(int) >= start) & (filtered_df["POS"].astype(int) <= end)
                ]
            else:
                pos = int(pos_filter)
                filtered_df = filtered_df[filtered_df["POS"].astype(int) == pos]
        except:
            st.warning("Filtro de posição inválido. Use apenas números ou intervalo no formato início-fim.")

    total_rows = filtered_df.shape[0]
    total_pages = max(1, math.ceil(total_rows / per_page))
    with col_filters:
        page = st.number_input("Página", min_value=1, max_value=total_pages, step=1)

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_df = filtered_df.iloc[start_idx:end_idx]

    if "genotype_edits" not in st.session_state:
        st.session_state.genotype_edits = {}

    with col_main:
        for idx, row in paginated_df.iterrows():
            key = f"{row['CHROM']}:{row['POS']}_{sample_name}"
            original_gt = row[sample_name]
            current_value = st.session_state.genotype_edits.get(key, original_gt)
            new_gt = st.text_input(f"{row['CHROM']}:{row['POS']}", value=current_value, key=f"edit_{key}")
            st.session_state.genotype_edits[key] = new_gt

        if st.button("Aplicar alterações"):
            for key, new_gt in st.session_state.genotype_edits.items():
                chrom_pos, sample = key.split("_")
                chrom, pos = chrom_pos.split(":")
                match = (df["CHROM"] == chrom) & (df["POS"] == pos)
                df.loc[match, sample] = new_gt

            st.session_state.df_modified = df.copy()
            st.success("Genótipos atualizados!")

def save_vcf(df, header_lines, column_line):
    output = io.StringIO()
    for line in header_lines:
        output.write(line + "\n")
    output.write(column_line + "\n")
    for _, row in df.iterrows():
        output.write("\t".join(map(str, row.values)) + "\n")
    return output.getvalue()

def compress_vcf(vcf_text):
    out_io = io.BytesIO()
    with gzip.GzipFile(fileobj=out_io, mode="wb") as f:
        f.write(vcf_text.encode("utf-8"))
    return out_io.getvalue()

def main():
    st.set_page_config(layout="wide")
    st.title("VCF SUPER TURBO BOMBA PATCH V2.6 🔬")

    file = archive_uploader()

    if file is not None:
        try:
            if "df_original" not in st.session_state:
                df, header_lines, column_line = parse_vcf(file)
                st.session_state.df_original = df
                st.session_state.header_lines = header_lines
                st.session_state.column_line = column_line
                st.session_state.df_modified = df.copy()

            df = st.session_state.df_modified

            st.write("### Visualizar variantes")
            num_linhas = st.number_input("Número de linhas para exibir", min_value=1, max_value=len(df), value=50)
            st.dataframe(df.head(num_linhas), use_container_width=True)

            sample_cols = df.columns[9:].tolist()
            if not sample_cols:
                st.warning("Nenhuma amostra encontrada após FORMAT.")
                return

            sample = st.selectbox("Selecione a amostra para edição:", sample_cols)
            edit_sample_genotypes(df, sample)

            st.write("### Gerar e baixar arquivo VCF")
            if st.button("Gerar arquivo para download"):
                vcf_text = save_vcf(st.session_state.df_modified, st.session_state.header_lines, st.session_state.column_line)

                col1, col2 = st.columns(2)
                with col1:
                    st.download_button("📥 Baixar VCF (texto)", data=vcf_text, file_name="vcf_editado.vcf", mime="text/vcf")

                with col2:
                    gzipped_vcf = compress_vcf(vcf_text)
                    st.download_button("📥 Baixar VCF compactado (.vcf.gz)", data=gzipped_vcf, file_name="vcf_editado.vcf.gz", mime="application/gzip")

        except Exception as e:
            st.error(f"Erro ao processar o VCF: {e}")

if __name__ == "__main__":
    main()
