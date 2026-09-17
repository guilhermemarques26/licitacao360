from PyQt6.QtCore import *
from modules.atas.widgets.worker_homologacao import Worker 
from PyQt6.QtWidgets import QFileDialog, QMessageBox
import pandas as pd

class GerarAtasController(QObject): 
    def __init__(self, icons, view, model):
        super().__init__()
        self.icons = icons
        self.view = view
        self.model = model.setup_model("controle_atas")
        self.worker = None
        self.setup_connections()

    def setup_connections(self):
        # Conecta o sinal de instruções
        self.view.instructionSignal.connect(self.instrucoes)
        self.view.trSignal.connect(self.termo_referencia)
        self.view.homologSignal.connect(self.termo_homologacao)
        self.view.sicafSignal.connect(self.sicaf_widget)
        self.view.atasSignal.connect(self.gerar_atas)

        # --- NOVAS CONEXÕES DO TERMO DE REFERÊNCIA ---
        self.view.tr_widget.configurarSqlModelSignal.connect(self.configurar_sql_model)
        
        # Intercepta os SINAIS da View
        self.view.tr_widget.dadosExtraidosSignal.connect(self.atualizar_banco_com_df)
        self.view.tr_widget.limparTabelaSignal.connect(self.limpar_tabela) # <-- NOVA CONEXÃO AQUI
        
        # Conecta o sinal `tabelaCarregada` para configurar o modelo SQL após carregar a tabela
        self.model.tabelaCarregada.connect(self.configurar_sql_model)

        if hasattr(self.view.homolog_widget, 'gerarPlanilhaBaseClicked'):
             self.view.homolog_widget.gerarPlanilhaBaseClicked.connect(self.iniciar_geracao_planilha_base)

    def limpar_tabela(self):
        """
        Função para esvaziar todos os registros do banco de dados atrelado à tabela atual.
        """
        resposta = QMessageBox.question(
            self.view.tr_widget,
            "Confirmar Limpeza",
            "Tem certeza de que deseja apagar todos os itens da tabela atual?\nIsso não pode ser desfeito.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if resposta == QMessageBox.StandardButton.Yes:
            # Remove as linhas de trás para frente para evitar perda de índice
            num_rows = self.model.rowCount()
            for i in range(num_rows - 1, -1, -1):
                self.model.removeRow(i)
            
            # Submete a transação para o banco de dados
            if self.model.submitAll():
                self.model.select()  # Recarrega a view para refletir que a tabela está vazia
            else:
                QMessageBox.warning(
                    self.view.tr_widget, 
                    "Erro", 
                    f"Erro ao limpar banco de dados: {self.model.lastError().text()}"
                )
    
    def atualizar_banco_com_df(self, df):
        """
        Recebe o DataFrame do PDF extraído e injeta no modelo SQL para exibição.
        """
        if df.empty:
            return

        # 1. CORREÇÃO: Limpa os registros antigos da mesma forma segura
        num_rows = self.model.rowCount()
        for i in range(num_rows - 1, -1, -1):
            self.model.removeRow(i)
        self.model.submitAll()

        # 2. Itera sobre as linhas do Pandas e insere no modelo SQL da PyQt
        for index, row in df.iterrows():
            record = self.model.record()
            record.setValue("item", str(row['item']))
            record.setValue("catalogo", str(row['catalogo']))
            record.setValue("descricao", str(row['descricao']))
            record.setValue("descricao_detalhada", str(row['descricao_detalhada']))
            
            # Insere o registro na última linha
            self.model.insertRecord(-1, record)
        
        # 3. Confirma a transação no banco e recarrega a visualização
        if self.model.submitAll():
            self.model.select() # Dá um "refresh" na View
        else:
            print(f"Erro ao salvar no banco: {self.model.lastError().text()}")


    def iniciar_geracao_planilha_base(self):
        pdf_dir = self.view.homolog_widget.pdf_dir
        if not pdf_dir or not pdf_dir.exists():
            print("Erro: O diretório de PDFs não foi selecionado.")
            return

        self.worker = Worker(pdf_dir=pdf_dir, modo='tabela_base')
        self.worker.progress_signal.connect(self.view.homolog_widget.update_progress)
        self.worker.update_context_signal.connect(self.view.homolog_widget.update_context)
        self.worker.finished.connect(self.finalizar_worker)
        self.worker.tabela_base_pronta.connect(self.salvar_planilha_base)
        self.worker.start()
        self.view.homolog_widget.set_buttons_enabled(False)
    
    def salvar_planilha_base(self, df):
        if df.empty:
            print("AVISO: O DataFrame está vazio. Nenhum arquivo será salvo.")
            return

        caminho_inicial = "planilha_base_licitacao.xlsx"
        caminho_arquivo, _ = QFileDialog.getSaveFileName(
            self.view,
            "Salvar Planilha Base",
            caminho_inicial,
            "Arquivos Excel (*.xlsx);;Todos os Arquivos (*)"
        )

        if caminho_arquivo:
            try:
                df.to_excel(caminho_arquivo, index=False)
                self.view.homolog_widget.update_context(f"Sucesso! Planilha salva em: {caminho_arquivo}")
            except Exception as e:
                self.view.homolog_widget.update_context(f"ERRO ao salvar a planilha: {e}")

    def finalizar_worker(self):
        self.view.homolog_widget.update_context("Processo finalizado.")
        self.view.homolog_widget.set_buttons_enabled(True)
        self.worker = None 

    def configurar_sql_model(self):
        self.view.tr_widget.table_view.setModel(self.model)
        self.view.configurar_visualizacao_tabela_tr(self.view.tr_widget.table_view)

    def instrucoes(self):
        self.view.content_area.setCurrentWidget(self.view.instrucoes_widget)

    def termo_referencia(self):
        self.view.content_area.setCurrentWidget(self.view.tr_widget)
        self.view.tr_widget.table_view.setModel(self.model)
        self.view.configurar_visualizacao_tabela_tr(self.view.tr_widget.table_view)

    def termo_homologacao(self):
        self.view.content_area.setCurrentWidget(self.view.homolog_widget)

    def sicaf_widget(self):
        self.view.content_area.setCurrentWidget(self.view.sicaf_widget)

    def gerar_atas(self):
        self.view.content_area.setCurrentWidget(self.view.atas_widget)