from PyQt6.QtCore import *
from PyQt6.QtWidgets import QProgressDialog, QMessageBox, QFileDialog, QApplication
from modules.atas.widgets.worker_homologacao import Worker 

class GerarAtasController(QObject): 
    def __init__(self, icons, view, model):
        super().__init__()
        self.icons = icons
        self.view = view
        self.model = model.setup_model("controle_atas")
        self.worker = None
        self.setup_connections()

    def setup_connections(self):
        self.view.instructionSignal.connect(self.instrucoes)
        self.view.trSignal.connect(self.termo_referencia)
        self.view.homologSignal.connect(self.termo_homologacao)
        self.view.sicafSignal.connect(self.sicaf_widget)
        self.view.atasSignal.connect(self.gerar_atas)

        self.view.tr_widget.abrirTabelaNova.connect(self.abrir_tabela_nova)
        self.view.tr_widget.configurarSqlModelSignal.connect(self.configurar_sql_model)

        self.view.tr_widget.carregarTabela.connect(self.caregar_tabela_com_dados)
        self.model.tabelaCarregada.connect(self.configurar_sql_model)

        if hasattr(self.view.homolog_widget, 'gerarPlanilhaBaseClicked'):
             self.view.homolog_widget.gerarPlanilhaBaseClicked.connect(self.iniciar_geracao_planilha_base)
    
    def iniciar_geracao_planilha_base(self):
        pdf_dir = self.view.homolog_widget.pdf_dir
        if not pdf_dir or not pdf_dir.exists():
            print("Erro: O diretório de PDFs não foi selecionado.")
            return

        self.worker = Worker(pdf_dir=pdf_dir, modo='tabela_base')
        self.worker.progress_signal.connect(self.view.homolog_widget.progress_bar.setValue)
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

    # ========================================================
    # ANIMAÇÕES DE CARREGAMENTO ADICIONADAS
    # ========================================================
    def abrir_tabela_nova(self):
        loading = QProgressDialog("Gerando e abrindo a nova planilha Excel...\nPor favor, aguarde.", None, 0, 0, self.view)
        loading.setWindowTitle("Processando")
        loading.setWindowModality(Qt.WindowModality.WindowModal)
        loading.setMinimumDuration(0) 
        loading.show()
        QApplication.processEvents()
        try:
            self.model.abrir_tabela_nova()
        except Exception as e:
            QMessageBox.critical(self.view, "Erro", f"Erro ao abrir tabela vazia: {e}")
        finally:
            loading.close()

    def caregar_tabela_com_dados(self):
        loading = QProgressDialog("Lendo a planilha e atualizando o banco de dados...\nPor favor, aguarde.", None, 0, 0, self.view)
        loading.setWindowTitle("Processando")
        loading.setWindowModality(Qt.WindowModality.WindowModal)
        loading.setMinimumDuration(0) 
        loading.show()
        QApplication.processEvents()
        try:
            self.model.carregar_tabela()
        except Exception as e:
            QMessageBox.critical(self.view, "Erro", f"Erro ao importar tabela: {e}")
        finally:
            loading.close()

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