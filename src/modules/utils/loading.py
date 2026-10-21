from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPainter, QColor, QPixmap
from pathlib import Path

from paths import ICONS_DIR

class LoadingOverlay(QWidget):
    """
    Widget de sobreposição semitransparente com a seta original do Licitação 360 girando.
    Bloqueia cliques na interface por baixo enquanto carrega.
    """
    def __init__(self, parent=None, texto="Processando..."):
        super().__init__(parent)
        self.texto = texto
        self.angulo = 0
        
        # Carrega a imagem da seta do Licitação 360
        caminho_imagem = ICONS_DIR / "loadingarrow.png"
        if caminho_imagem.exists():
            # Redimensiona para um tamanho adequado mantendo a qualidade
            self.pixmap_logo = QPixmap(str(caminho_imagem)).scaled(
                80, 80, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
        else:
            self.pixmap_logo = None
            print(f"Aviso interno: Imagem do spinner não encontrada em {caminho_imagem}")

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotacionar)
        
        # Oculto por padrão
        self.hide()

    def rotacionar(self):
        # Aumenta o ângulo a cada "tick" para criar a rotação. 
        # O valor 6 em vez de 10 deixa o giro mais fluido a 60 FPS.
        self.angulo = (self.angulo + 6) % 360
        self.update() # Força a tela a redesenhar

    def start(self, texto_novo=None):
        if texto_novo:
            self.texto = texto_novo
            
        # Redimensiona para cobrir exatamente a janela/widget pai
        if self.parent():
            self.resize(self.parent().size())
            
        self.show()
        self.raise_() # Traz para a frente de tudo
        
        # 16 milissegundos equivale a ~60 FPS para uma rotação super fluida
        self.timer.start(16) 

    def stop(self):
        self.timer.stop()
        self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing) 
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform) # Suaviza a rotação da imagem

        # 1. Desenha o fundo escuro semitransparente (Alpha 180)
        painter.fillRect(self.rect(), QColor(10, 10, 15, 180))

        # Configura o centro da tela
        cx = self.width() // 2
        cy = self.height() // 2

        # 2. Desenha a Imagem Rodando (se ela existir)
        if self.pixmap_logo:
            painter.save()
            
            # Move o eixo central para o meio da tela
            painter.translate(cx, cy)
            
            # Gira o próprio eixo
            painter.rotate(self.angulo)
            
            # Desenha a imagem exatamente no centro
            w = self.pixmap_logo.width()
            h = self.pixmap_logo.height()
            painter.drawPixmap(-w // 2, -h // 2, self.pixmap_logo)
            
            painter.restore()
            
            espaco_imagem = (h // 2) + 25
        else:
            espaco_imagem = 30

        # 3. Desenha o texto sem limites rígidos para não cortar
        if self.texto:
            painter.setPen(QColor("white"))
            font = painter.font()
            font.setPointSize(14)
            font.setBold(True)
            painter.setFont(font)
            
            # Pega as métricas da fonte para saber o tamanho exato da frase lida
            font_metrics = painter.fontMetrics()
            largura_texto = font_metrics.horizontalAdvance(self.texto)
            altura_texto = font_metrics.height()
            
            # Cria uma caixa de desenho invisível baseada no tamanho exato da frase
            rect_texto = QRectF(
                cx - (largura_texto / 2), 
                cy + espaco_imagem, 
                largura_texto, 
                altura_texto + 10
            )
            
            # O PyQt agora desenha centralizado na caixa que tem largura infinita/dinâmica
            painter.drawText(rect_texto, Qt.AlignmentFlag.AlignCenter, self.texto)

    # Bloqueia qualquer evento de clique de passar para a tela de baixo
    def mousePressEvent(self, event):
        event.accept()