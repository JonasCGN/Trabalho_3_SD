# Video Processor Client

Este é um cliente GUI desenvolvido com Tkinter para processamento de vídeos distribuído.

## Funcionalidades

### 1. Seleção de Arquivo de Vídeo
- Interface intuitiva para selecionar arquivos de vídeo
- Suporte para formatos: MP4, AVI, MOV, MKV, FLV, WMV
- Exibição do nome do arquivo e tamanho selecionado

### 2. Envio via HTTP com Filtros
- Envio de vídeos para o servidor via requisições HTTP POST
- Seleção de filtros disponíveis:
  - **Grayscale**: Converte o vídeo para escala de cinza
  - **Blur**: Aplica efeito de desfoque
  - **Edge Detection**: Detecção de bordas
  - **Brightness +50**: Aumenta o brilho
  - **Sepia**: Aplica efeito sépia

### 3. Visualização de Vídeos
- **Preview Original**: Abre o vídeo original no player padrão do sistema
- **Preview Processed**: Abre o vídeo processado no player padrão do sistema
- Botões habilitados automaticamente quando os arquivos estão disponíveis

### 4. Histórico de Vídeos
- **Aba History**: Lista todos os vídeos já processados
- **Informações exibidas**:
  - ID do vídeo (primeiros 8 caracteres)
  - Nome original do arquivo
  - Filtro aplicado
  - Data e hora de criação
  - Duração do vídeo
  - Tamanho do arquivo
- **Detalhes completos**: Duplo-clique em um item para ver informações detalhadas
- **Atualização automática**: Histórico é atualizado após cada processamento
- **Limpar histórico**: Opção para remover todos os registros

## Como Usar

### Método 1: Linha de Comando
```bash
cd "caminho/para/Trabalho_3_SD"
python frontend/main.py
```

### Passo a Passo para Processar um Vídeo

1. **Selecionar Arquivo**:
   - Clique em "Browse" na seção "Select Video File"
   - Escolha um arquivo de vídeo do seu computador
   - O nome e tamanho do arquivo serão exibidos

2. **Escolher Filtro**:
   - Selecione um dos filtros disponíveis na seção "Select Filter"
   - O filtro padrão é "Grayscale"

3. **Enviar e Processar**:
   - Clique em "Upload & Process Video"
   - Acompanhe o progresso na barra de carregamento
   - Veja o status em tempo real na área de log

4. **Visualizar Resultados**:
   - Use "Preview Original" para ver o vídeo original
   - Use "Preview Processed" para ver o vídeo processado (disponível após o processamento)

5. **Consultar Histórico**:
   - Vá para a aba "History" para ver todos os vídeos processados
   - Duplo-clique em um item para ver detalhes completos
   - Use "Refresh History" para atualizar a lista
   - Use "Clear History" para limpar todos os registros

## Configuração do Servidor

Por padrão, o cliente tenta se conectar a `http://localhost:8000`. Para alterar:

1. Abra o arquivo `frontend/main.py`
2. Localize a linha `self.server_url = "http://localhost:8000"`
3. Altere para o endereço do seu servidor

## Requisitos

- Python 3.6+
- Tkinter (incluído com Python)
- Requests library
- SQLite3 (incluído com Python)

Para instalar dependências:
```bash
pip install -r requirements.txt
```

## Estrutura do Banco de Dados

O cliente utiliza um banco SQLite (`videos.db`) para armazenar o histórico, com as seguintes informações:
- ID único do vídeo
- Nome e extensão do arquivo original
- Tipo MIME e tamanho
- Duração, FPS e resolução
- Filtro aplicado
- Data de criação
- Caminhos dos arquivos original e processado

## Resolução de Problemas

### "Network error" ou "Upload failed"
- Verifique se o servidor está executando
- Confirme o endereço do servidor no código
- Verifique sua conexão de rede

### "Failed to open video"
- Verifique se você tem um player de vídeo instalado
- Confirme se o arquivo de vídeo existe no local especificado

### "Database Error"
- O banco de dados será criado automaticamente na primeira execução
- Verifique as permissões de escrita no diretório do projeto

## Interface

A interface é dividida em duas abas principais:

### Aba "Process Video"
- Seleção de arquivo
- Escolha de filtro
- Upload e processamento
- Log de status em tempo real
- Botões de preview

### Aba "History"
- Lista de todos os vídeos processados
- Área de detalhes do vídeo selecionado
- Controles para atualizar e limpar histórico
