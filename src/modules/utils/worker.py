from PyQt6.QtCore import QObject, pyqtSignal

class GenericWorker(QObject):
    """
    Trabalhador genérico para rodar funções pesadas em segundo plano.
    Emite sinais para a interface principal quando termina ou encontra erros.
    """
    # Sinais para comunicar com a interface (UI)
    finished = pyqtSignal(object)  # Envia o resultado final da função
    error = pyqtSignal(str)        # Envia a mensagem de erro, se falhar

    def __init__(self, funcao_pesada, *args, **kwargs):
        super().__init__()
        self.funcao_pesada = funcao_pesada
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            # Executa a leitura de PDFs, cruzamento de dados, etc.
            resultado = self.funcao_pesada(*self.args, **self.kwargs)
            
            # Avisa a tela que terminou e envia o resultado
            self.finished.emit(resultado)
        except Exception as e:
            # Em caso de crash, avisa a tela e envia o erro
            self.error.emit(str(e))