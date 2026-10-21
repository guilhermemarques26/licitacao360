import re
from PyQt6.QtWidgets import QTextEdit, QMenu
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QTextCursor
from PyQt6.QtCore import Qt

class SpellHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        # Inicializa o dicionário em Português
        try:
            from spellchecker import SpellChecker
            self.spell = SpellChecker(language='pt')
        except ImportError:
            self.spell = None
            print("Aviso: pyspellchecker não instalado.")

        # Formatação do erro: Linha ondulada vermelha
        self.error_format = QTextCharFormat()
        self.error_format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
        self.error_format.setUnderlineColor(QColor("red"))

    def highlightBlock(self, text):
        if not self.spell:
            return

        # Expressão regular para capturar palavras em português (com acentos)
        word_pattern = re.compile(r'\b[a-zA-ZáàãâéêíóõôúçÁÀÃÂÉÊÍÓÕÔÚÇ]+\b')
        
        for match in word_pattern.finditer(text):
            word = match.group()
            # Ignora palavras todas em maiúsculas (geralmente siglas)
            if word.isupper():
                continue
                
            # Verifica se a palavra está errada
            if self.spell.unknown([word.lower()]):
                self.setFormat(match.start(), match.end() - match.start(), self.error_format)

class SpellTextEdit(QTextEdit):
    """
    Uma caixa de texto (QTextEdit) com corretor ortográfico integrado.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.highlighter = SpellHighlighter(self.document())
        self.spell = self.highlighter.spell

    def contextMenuEvent(self, event):
        # Cria o menu padrão do botão direito (Copiar, Colar, etc.)
        menu = self.createStandardContextMenu()
        
        if self.spell:
            # Pega a palavra onde o utilizador clicou
            cursor = self.cursorForPosition(event.pos())
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
            word = cursor.selectedText()

            # Se a palavra clicada estiver errada, adiciona sugestões no topo do menu
            if word and not word.isupper() and self.spell.unknown([word.lower()]):
                suggestions = self.spell.candidates(word.lower())
                
                if suggestions:
                    # Adiciona título ao menu
                    title_action = menu.addAction("Sugestões:")
                    title_action.setEnabled(False)
                    
                    # Pega até 5 sugestões
                    for suggestion in list(suggestions)[:5]:
                        # Mantém a capitalização original (Se era 'Teste', sugere 'Texto' e não 'texto')
                        if word.istitle():
                            suggestion = suggestion.capitalize()
                            
                        action = menu.addAction(suggestion)
                        # Conecta o clique à substituição da palavra
                        action.triggered.connect(lambda checked, s=suggestion, c=cursor: self._replace_word(c, s))
                    
                    menu.addSeparator()

        # Exibe o menu
        menu.exec(event.globalPos())

    def _replace_word(self, cursor, new_word):
        # Substitui a palavra errada pela sugestão escolhida
        cursor.insertText(new_word)