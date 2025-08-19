import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime, date
import pytz
import re
import os
from streamlit_oauth import OAuth2Component
from oauth2client.service_account import ServiceAccountCredentials
import requests
from dotenv import load_dotenv

load_dotenv()

# --- Configurações de Autenticação do Google ---
CLIENT_ID = os.getenv("cliente_id")
CLIENT_SECRET = os.getenv("cliente_secret")
AUTHORIZE_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"

# --- E-mails com permissão de acesso ---
EMAILS_AUTORIZADOS = [
    "victor.oliveira@quantaconsultoria.com",
    "hagata@gmail.com",
    # Adicione outros e-mails autorizados aqui
]

# --- Configuração da Página Streamlit ---
st.set_page_config(page_title="Gerenciador de Tarefas", page_icon="icone-quanta.png", layout="wide")
st.logo("logo-quanta-oficial.png", size="large")

# --- Componente de Autenticação OAuth2 ---
oauth2 = OAuth2Component(CLIENT_ID, CLIENT_SECRET, AUTHORIZE_ENDPOINT, TOKEN_ENDPOINT, TOKEN_ENDPOINT, REVOKE_ENDPOINT)

# --- Lógica de Login ---
if 'token' not in st.session_state:
    # Se não há token na sessão, mostra o botão de login
    result = oauth2.authorize_button(
        name="Continuar com o Google",
        icon="https://www.google.com.br/favicon.ico",
        redirect_uri="http://localhost:8501", # Deve ser o mesmo URI de redirecionamento configurado no Google Cloud
        scope="openid email profile",
        key="google",
        use_container_width=True,
        pkce='S256',
    )
    if result:
        st.session_state['token'] = result.get('token')
        st.rerun()
else:
    # --- Se o usuário está logado ---
    token = st.session_state['token']
    
    # Endpoint para buscar informações do usuário do Google
    user_info_endpoint = "https://www.googleapis.com/oauth2/v1/userinfo"
    
    # Cabeçalho de autorização com o token de acesso
    headers = {'Authorization': f'Bearer {token["access_token"]}'}
    
    user_email = None # Inicializa a variável
    try:
        # Faz a chamada GET para a API do Google
        user_info_response = requests.get(user_info_endpoint, headers=headers)
        user_info_response.raise_for_status() # Lança um erro para códigos de status ruins (4xx ou 5xx)
        user_info = user_info_response.json()
        user_email = user_info.get('email')

    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao buscar informações do usuário: {e}")
        # Oferece uma opção de logout para tentar novamente
        if st.button("Sair e tentar novamente"):
            del st.session_state['token']
            st.rerun()
        st.stop() # Para a execução se não conseguir pegar o e-mail

    # --- Verificação de Autorização e Lógica Principal ---
    if user_email and user_email in EMAILS_AUTORIZADOS:
        st.sidebar.write(f"Logado como: {user_email}")

        # Lista de autores para o filtro
        lista_autores = ["ALEXANDRE", "ARQ QUANTA", "BBRUNO MATHIAS", "BRUNO ALMEIDA", "BRUNO MATHIAS", "CAMILA", "CAROLINA", "GABRIEL M", "GABRIEL M. / MATHEUS F./CAROL", "GABRIEL MEURER", "IVANESSa", "KAYKE CHELI", "LEO", "MATHEUS F.", "MATHEUS FERREIRA", "TARCISIO", "TERCEIRIZADO - CAURIN", "TERCEIRIZADO - TEKRA", "THATY", "THATY E CAROL", "VANESSA", "VINICIUS COORD", "VITINHO", "WANDER"]

        SCOPE = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']

        # --- Funções Auxiliares ---

        # 🔐 Autenticando com o Google Sheets
        @st.cache_resource # Use cache para a conexão
        def autenticar_google_sheets():
            try:
                creds = ServiceAccountCredentials.from_json_keyfile_name('credenciais.json', SCOPE)
                client = gspread.authorize(creds)
                # Abre a planilha pela chave (key)
                sheet = client.open_by_key('1ZzMXgfnGvplabe9eNDCUXUbjuCXLieSgbpPUqAtBYOU').sheet1
                return sheet
            except Exception as e:
                st.error(f"Erro ao autenticar com o Google Sheets: {e}")
                return None

        # Define a ordem e nome das colunas esperadas na planilha
        colunas_esperadas = [
            "% CONCLUIDA", "MEMORIAL DE CÁLCULO", "MEMORIAL DE DESCRITIVO", "EDT", "OS",
            "PRODUTO", "NOME DA OS", "TIPO DE PROJETO", "NOME DA TAREFA", "DISCIPLINA",
            "SUBDISCIPLINA", "AUTOR", "RESPONSAVEL TÉCNICO (Lider)", "INÍCIO CONTRATUAL",
            "TÉRMINO CONTRATUAL", "INÍCIO REAL", "TÉRMINO REAL", "DATA REVISÃO DOC",
            "DATA REVISÃO PROJETO", "DURAÇÃO PLANEJADA (DIAS)", "DURAÇÃO REAL (DIAS)",
            "% AVANÇO PLANEJADO", "% AVANÇO REAL", "HH Orçado", "BCWS_HH", "BCWP_HH",
            "ACWP_HH", "SPI_HH", "CPI_HH", "EAC_HH", "OBSERVAÇÕES", "EMAIL"
        ]
        
        def carregar_dados(sheet):
            """Carrega e pré-processa os dados da planilha."""
            try:
                dados = sheet.get_all_records(expected_headers=colunas_esperadas)
            except gspread.exceptions.GSpreadException as e:
                st.error(f"Erro ao carregar dados da planilha. Verifique se a lista 'colunas_esperadas' no código corresponde EXATAMENTE aos cabeçalhos e número de colunas na sua planilha. Detalhes: {e}")
                st.stop()
            
            df = pd.DataFrame(dados)
            
            # Força colunas de texto para string para evitar erros de tipo
            text_cols_to_force_str = [
                "EDT", "OS", "NOME DA TAREFA", "MEMORIAL DE CÁLCULO", "MEMORIAL DE DESCRITIVO", 
                "PRODUTO", "NOME DA OS", "TIPO DE PROJETO", "DISCIPLINA", "SUBDISCIPLINA", 
                "AUTOR", "RESPONSAVEL TÉCNICO (Lider)", "HH Orçado", "BCWS_HH", "BCWP_HH", 
                "ACWP_HH", "SPI_HH", "CPI_HH", "EAC_HH", "OBSERVAÇÕES", "EMAIL"
            ]
            for col in text_cols_to_force_str:
                if col in df.columns:
                    df[col] = df[col].astype(str).fillna('') 
                    
            # Força colunas numéricas
            numeric_cols_to_force_num = [
                "DURAÇÃO PLANEJADA (DIAS)", "DURAÇÃO REAL (DIAS)"
            ]
            for col in numeric_cols_to_force_num:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
            # Converte colunas de percentual para float
            for col in ["% CONCLUIDA", "% AVANÇO PLANEJADO", "% AVANÇO REAL"]:
                if col in df.columns:
                    df[col] = df[col].apply(parse_percent_string)

            # Converte colunas de data
            date_cols = ["INÍCIO CONTRATUAL", "TÉRMINO CONTRATUAL", "INÍCIO REAL", "TÉRMINO REAL", 
                         "DATA REVISÃO DOC", "DATA REVISÃO PROJETO"]
            for col in date_cols:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: None if str(x).strip() == '' else x)
                    df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True)
            
            # Extrai o nome base do autor sem o timestamp para o filtro
            if "AUTOR" in df.columns:
                df['AUTOR_BASE'] = df['AUTOR'].apply(lambda x: re.sub(r'\s*\(Editado em \d{2}/\d{2}/\d{4} \d{2}:\d{2}\)$', '', x) if isinstance(x, str) else x)
                df['AUTOR_BASE'] = df['AUTOR_BASE'].str.upper()

            return df

        def get_column_letter(n):
            """Converte um número de coluna em letra do Google Sheets (A, B, ..., Z, AA, AB, etc.)."""
            result = ""
            while n:
                n, remainder = divmod(n - 1, 26)
                result = chr(65 + remainder) + result
            return result

        def atualizar_linha(sheet, idx, nova_linha_valores):
            """Atualiza uma linha específica na planilha."""
            try:
                coluna_final = get_column_letter(len(nova_linha_valores))
                range_name = f"A{idx}:{coluna_final}{idx}"
                
                sheet.update(values=[nova_linha_valores], range_name=range_name)
                return True
            except Exception as e:
                print(f"Erro ao atualizar a linha {idx}: {e}")
                st.error(f"Erro ao atualizar a linha: {e}. Verifique o console para mais detalhes.")
                return False

        def parse_percent_string(percent_str):
            """Converte uma string de percentual para float."""
            try:
                if isinstance(percent_str, (int, float)):
                    return float(percent_str)
                if isinstance(percent_str, str):
                    cleaned_str = percent_str.replace('%', '').replace(',', '.').strip()
                    if cleaned_str:
                        return float(cleaned_str)
                return 0.0
            except ValueError:
                return 0.0


        st.title("Gerenciador de Planilha")

        sheet = autenticar_google_sheets()
        if not sheet:
            st.stop()

        # Verificação inicial das colunas
        temp_df_check = carregar_dados(sheet)
        for col_check in ["EDT", "OS", "NOME DA TAREFA"]:
            if col_check not in temp_df_check.columns:
                st.error(f"A coluna '{col_check}' é essencial e não foi encontrada. Verifique a lista 'colunas_esperadas' ou sua planilha.")
                st.stop()
        colunas_faltando = [col for col in colunas_esperadas if col not in temp_df_check.columns]
        if colunas_faltando:
            st.warning(f"⚠️ As seguintes colunas estão faltando na sua lista de 'colunas_esperadas' ou na planilha: {', '.join(colunas_faltando)}. Por favor, adicione-as.")
        del temp_df_check

        # --- Abas da Aplicação ---
        aba = st.sidebar.radio("Escolha uma opção:", ["Editar Tarefa", "Visualizar Tarefas"])

        # --- Seção Editar Tarefa ---
        if aba == "Editar Tarefa":
            st.header("✏️ Editar Tarefa")

            autor_filtro = st.selectbox("Selecione o autor para filtrar suas tarefas:", [""] + sorted(lista_autores))

            if autor_filtro:
                dados_df = carregar_dados(sheet)
                
                # Filtra as tarefas do autor que não estão 100% concluídas
                autor_filtro_upper = autor_filtro.upper()
                df_usuario = dados_df[
                    (dados_df["AUTOR_BASE"] == autor_filtro_upper) & 
                    (dados_df["% CONCLUIDA"] < 100.0)
                ]

                if df_usuario.empty:
                    st.warning("Nenhuma tarefa encontrada para este usuário ou todas as tarefas estão 100% concluídas.")
                else:
                    # Cria as opções para o selectbox de tarefas
                    opcoes_exibidas = [
                        f"OS: {os_val} / EDT: {num} / Tarefa: {nome}"
                        for os_val, num, nome in zip(df_usuario["OS"], df_usuario["EDT"], df_usuario["NOME DA TAREFA"])
                    ]
                    
                    # Mapeia a string de exibição para o índice no dataframe filtrado
                    mapa_string_para_indice_df = {
                        f"OS: {os_val} / EDT: {num} / Tarefa: {nome}": idx
                        for idx, (os_val, num, nome) in enumerate(zip(df_usuario["OS"], df_usuario["EDT"], df_usuario["NOME DA TAREFA"]))
                    }

                    selecionado_exibido = st.selectbox("Selecione a Tarefa:", options=opcoes_exibidas, index=0)

                    if selecionado_exibido:
                        # Pega os dados da tarefa selecionada
                        indice_no_df_usuario = mapa_string_para_indice_df[selecionado_exibido]
                        tarefa = df_usuario.iloc[indice_no_df_usuario].copy()
                            
                        # Encontra o índice da linha na planilha original (DataFrame completo)
                        matched_rows_mask = (
                                (dados_df["OS"].astype(str) == str(tarefa["OS"])) &
                                (dados_df["EDT"].astype(str) == str(tarefa["EDT"])) &
                                (dados_df["NOME DA TAREFA"].astype(str) == str(tarefa["NOME DA TAREFA"]))
                        )

                        if not dados_df[matched_rows_mask].empty:
                            df_index = dados_df[matched_rows_mask].index[0]
                            linha_idx_para_atualizar = df_index + 2 # +2 porque a planilha é 1-based e tem cabeçalho
                        else:
                            st.error("Erro: A tarefa selecionada não pôde ser encontrada na planilha principal. Por favor, recarregue a página.")
                            st.stop()

                        st.info(f"Atualização na linha **{linha_idx_para_atualizar}** da planilha")

                        # Pega os valores antigos para lógica de atualização
                        perc_concluida_antiga = float(tarefa["% CONCLUIDA"])
                        inicio_real_antigo_value = pd.to_datetime(tarefa["INÍCIO REAL"], errors='coerce')
                        inicio_real_antigo_preenchido = pd.notnull(inicio_real_antigo_value)
                        inicio_contratual_valor = pd.to_datetime(tarefa["INÍCIO CONTRATUAL"], errors='coerce')
                        inicio_contratual_data = inicio_contratual_valor.date() if pd.notnull(inicio_contratual_valor) else None
                        termino_contratual_valor = pd.to_datetime(tarefa["TÉRMINO CONTRATUAL"], errors='coerce')
                        termino_contratual_data = termino_contratual_valor.date() if pd.notnull(termino_contratual_valor) else None
                        inicio_real_antigo = inicio_real_antigo_value.date() if inicio_real_antigo_preenchido else None
                        termino_real_antigo = pd.to_datetime(tarefa["TÉRMINO REAL"], errors='coerce').date() if pd.notnull(pd.to_datetime(tarefa["TÉRMINO REAL"], errors='coerce')) else None
                        data_revisao_doc_antiga = pd.to_datetime(tarefa["DATA REVISÃO DOC"], errors='coerce').date() if pd.notnull(pd.to_datetime(tarefa["DATA REVISÃO DOC"], errors='coerce')) else None
                        data_revisao_projeto_antiga = pd.to_datetime(tarefa["DATA REVISÃO PROJETO"], errors='coerce').date() if pd.notnull(pd.to_datetime(tarefa["DATA REVISÃO PROJETO"], errors='coerce')) else None

                        # --- Formulário de Edição ---
                        with st.form(key="editar_form"):
                            perc_concluida = st.number_input("% CONCLUIDA", min_value=0.0, max_value=100.0, step=0.1, value=perc_concluida_antiga, format="%.1f")
                            memorial_calculo = st.text_input("MEMORIAL DE CALCULO", str(tarefa["MEMORIAL DE CÁLCULO"]))
                            memorial_descritivo = st.text_input("MEMORIAL DE DESCRITIVO", str(tarefa["MEMORIAL DE DESCRITIVO"]))
                            num_hierarquico = st.text_input("EDT", str(tarefa["EDT"]), disabled=True, help="EDT não pode ser alterado.")
                            os_tarefa = st.text_input("OS", str(tarefa["OS"]), disabled=True, help="OS não pode ser alterado.")
                            produto = st.text_input("PRODUTO", str(tarefa["PRODUTO"]))
                            nome_os = st.text_input("NOME DA OS", str(tarefa["NOME DA OS"]))
                            tipo_projeto = st.text_input("TIPO DE PROJETO", str(tarefa["TIPO DE PROJETO"]))
                            nome_tarefa = st.text_input("NOME DA TAREFA", str(tarefa["NOME DA TAREFA"]), disabled=True, help="Nome da Tarefa não pode ser alterado.")
                            disciplina = st.text_input("DISCIPLINA", str(tarefa["DISCIPLINA"]))
                            subdisciplina = st.text_input("SUBDISCIPLINA", str(tarefa["SUBDISCIPLINA"]))
                            autor = st.text_input("AUTOR", str(tarefa["AUTOR"]), disabled=True) 
                            responsavel_tecnico = st.text_input("RESPONSAVEL TÉCNICO (Lider)", str(tarefa["RESPONSAVEL TÉCNICO (Lider)"]))
                            inicio_contratual = st.date_input("INÍCIO CONTRATUAL", value=inicio_contratual_data or date.today())
                            termino_contratual = st.date_input("TÉRMINO CONTRATUAL", value=termino_contratual_data or date.today())
                            duracao_planejada_val = int(tarefa["DURAÇÃO PLANEJADA (DIAS)"]) if pd.notnull(tarefa["DURAÇÃO PLANEJADA (DIAS)"]) else 0
                            duracao_planejada = st.number_input("DURAÇÃO PLANEJADA (DIAS)", min_value=0, value=duracao_planejada_val)
                            duracao_real_val = int(tarefa["DURAÇÃO REAL (DIAS)"]) if pd.notnull(tarefa["DURAÇÃO REAL (DIAS)"]) else 0
                            duracao_real = st.number_input("DURAÇÃO REAL (DIAS)", min_value=0, value=duracao_real_val)
                            avanco_planejado = st.number_input("% AVANÇO PLANEJADO", min_value=0.0, max_value=100.0, step=0.1, value=float(tarefa["% AVANÇO PLANEJADO"]))
                            avanco_real = st.number_input("% AVANÇO REAL", min_value=0.0, max_value=100.0, step=0.1, value=float(tarefa["% AVANÇO REAL"]))
                            hh_orcado = st.text_input("HH Orçado", str(tarefa["HH Orçado"]))
                            bcws_hh = st.text_input("BCWS_HH", str(tarefa["BCWS_HH"]))
                            bcwp_hh = st.text_input("BCWP_HH", str(tarefa["BCWP_HH"]))
                            acwp_hh = st.text_input("ACWP_HH", str(tarefa["ACWP_HH"]))
                            spi_hh = st.text_input("SPI_HH", str(tarefa["SPI_HH"]))
                            cpi_hh = st.text_input("CPI_HH", str(tarefa["CPI_HH"]))
                            eac_hh = st.text_input("EAC_HH", str(tarefa["EAC_HH"]))
                            observacoes = st.text_input("OBSERVAÇÕES", str(tarefa["OBSERVAÇÕES"]))
                            
                            atualizar = st.form_submit_button("Atualizar")

                            if atualizar:
                                # Validação para não zerar progresso se já iniciado
                                if perc_concluida_antiga > 0 and perc_concluida == 0 and inicio_real_antigo_preenchido:
                                    st.error("❌ Não é possível voltar o '% CONCLUIDA' para 0% se a tarefa já teve avanço e o 'INÍCIO REAL' foi preenchido.")
                                    st.stop()

                                # Pega a data e hora atual
                                fuso_brasilia = pytz.timezone("America/Sao_Paulo")
                                agora_completa = datetime.now(fuso_brasilia) 
                                agora_data = agora_completa.date() 

                                # Define INÍCIO REAL se a tarefa está começando
                                if perc_concluida_antiga == 0.0 and perc_concluida > 0.0:
                                    inicio_real_para_salvar = agora_data
                                else:
                                    inicio_real_para_salvar = inicio_real_antigo

                                # Define TÉRMINO REAL se a tarefa está sendo concluída
                                if perc_concluida_antiga < 100.0 and perc_concluida == 100.0:
                                    termino_real_para_salvar = agora_data
                                else:
                                    termino_real_para_salvar = termino_real_antigo
                                
                                data_revisao_doc_para_salvar = data_revisao_doc_antiga
                                data_revisao_projeto_para_salvar = data_revisao_projeto_antiga

                                # Adiciona timestamp ao nome do autor
                                autor_original_da_tarefa = str(tarefa["AUTOR"])
                                data_hora_edicao = agora_completa.strftime("%d/%m/%Y %H:%M")
                                
                                regex_timestamp = r'\s*\(Editado em \d{2}/\d{2}/\d{4} \d{2}:\d{2}\)$'
                                if re.search(regex_timestamp, autor_original_da_tarefa):
                                    autor_com_data_hora = re.sub(regex_timestamp, f' (Editado em {data_hora_edicao})', autor_original_da_tarefa)
                                else:
                                    autor_com_data_hora = f"{autor_original_da_tarefa} (Editado em {data_hora_edicao})"

                                # --- ALTERAÇÃO PRINCIPAL ---
                                # Junta o e-mail do usuário com a data e hora da atualização
                                email_com_timestamp = f"{user_email} (Atualizado em {data_hora_edicao})"

                                # Monta o dicionário com todos os valores para salvar
                                valores_para_salvar_dict = {
                                    "% CONCLUIDA": f"{perc_concluida:.1f}",
                                    "MEMORIAL DE CÁLCULO": memorial_calculo,
                                    "MEMORIAL DE DESCRITIVO": memorial_descritivo,
                                    "EDT": num_hierarquico,
                                    "OS": os_tarefa,
                                    "PRODUTO": produto,
                                    "NOME DA OS": nome_os,
                                    "TIPO DE PROJETO": tipo_projeto,
                                    "NOME DA TAREFA": nome_tarefa,
                                    "DISCIPLINA": disciplina,
                                    "SUBDISCIPLINA": subdisciplina,
                                    "AUTOR": autor_com_data_hora, 
                                    "RESPONSAVEL TÉCNICO (Lider)": responsavel_tecnico,
                                    "INÍCIO CONTRATUAL": inicio_contratual.strftime("%d/%m/%Y") if inicio_contratual else "",
                                    "TÉRMINO CONTRATUAL": termino_contratual.strftime("%d/%m/%Y") if termino_contratual else "",
                                    "INÍCIO REAL": inicio_real_para_salvar.strftime("%d/%m/%Y") if inicio_real_para_salvar else "",
                                    "TÉRMINO REAL": termino_real_para_salvar.strftime("%d/%m/%Y") if termino_real_para_salvar else "",
                                    "DATA REVISÃO DOC": data_revisao_doc_para_salvar.strftime("%d/%m/%Y") if data_revisao_doc_para_salvar else "",
                                    "DATA REVISÃO PROJETO": data_revisao_projeto_para_salvar.strftime("%d/%m/%Y") if data_revisao_projeto_para_salvar else "",
                                    "DURAÇÃO PLANEJADA (DIAS)": duracao_planejada,
                                    "DURAÇÃO REAL (DIAS)": duracao_real,
                                    "% AVANÇO PLANEJADO": f"{avanco_planejado:.1f}",
                                    "% AVANÇO REAL": f"{avanco_real:.1f}",
                                    "HH Orçado": hh_orcado,
                                    "BCWS_HH": bcws_hh,
                                    "BCWP_HH": bcwp_hh,
                                    "ACWP_HH": acwp_hh,
                                    "SPI_HH": spi_hh,
                                    "CPI_HH": cpi_hh,
                                    "EAC_HH": eac_hh,
                                    "OBSERVAÇÕES": observacoes,
                                    "EMAIL": email_com_timestamp # <--- Valor atualizado aqui
                                }
                                
                                # Converte o dicionário para uma lista na ordem correta das colunas
                                nova_linha_valores = [str(valores_para_salvar_dict.get(col, "")) for col in colunas_esperadas]

                                # Chama a função para atualizar a planilha
                                sucesso = atualizar_linha(sheet, linha_idx_para_atualizar, nova_linha_valores)
                                if sucesso:
                                    st.success("✅ Tarefa atualizada com sucesso!")
                                    st.rerun()
                                else:
                                    st.error("❌ Erro ao atualizar. Verifique o console para mais detalhes.")
        
        # --- Seção Visualizar Tarefas ---
        elif aba == "Visualizar Tarefas":
            st.header("📋 Visualização de Tarefas")
            dados_df = carregar_dados(sheet)
            
            if not dados_df.empty:
                dados_formatados = dados_df.copy()

                # Formata as colunas de data para exibição
                colunas_data = [
                    "INÍCIO CONTRATUAL", "TÉRMINO CONTRATUAL", "INÍCIO REAL", "TÉRMINO REAL",
                    "DATA REVISÃO DOC", "DATA REVISÃO PROJETO"
                ]
                for col in colunas_data:
                    if col in dados_formatados.columns:
                        dados_formatados[col] = dados_formatados[col].dt.strftime('%d/%m/%Y').fillna('')

                # Formata as colunas de percentual para exibição
                colunas_percentuais = [
                    "% CONCLUIDA", "% AVANÇO PLANEJADO", "% AVANÇO REAL"
                ]
                for col in colunas_percentuais:
                    if col in dados_formatados.columns:
                        dados_formatados[col] = (
                            dados_formatados[col].round(1).astype(str) + "%"
                        )
                
                # Converte outras colunas numéricas para string para exibição consistente
                for col in ["DURAÇÃO PLANEJADA (DIAS)", "DURAÇÃO REAL (DIAS)"]:
                    if col in dados_formatados.columns:
                        dados_formatados[col] = dados_formatados[col].astype(str)

                # Garante a ordem correta das colunas para exibição
                colunas_ordenadas = [col for col in colunas_esperadas if col in dados_formatados.columns]
                dados_formatados = dados_formatados[colunas_ordenadas]

                st.dataframe(dados_formatados, use_container_width=True)
            else:
                st.info("Nenhuma tarefa cadastrada ainda.")
    else:
        # Se o e-mail não estiver na lista, mostra uma mensagem de acesso negado
        st.error("❌ Acesso Negado!")
        st.write("Você não tem permissão para acessar esta aplicação ou não foi possível obter seu e-mail. Por favor, contate o administrador.")
        if st.button("Sair"):
            del st.session_state['token']
            st.rerun()
