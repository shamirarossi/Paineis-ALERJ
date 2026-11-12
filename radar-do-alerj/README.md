# Radar do Diário Oficial (ALERJ)

Leitura diária da **Parte II (Poder Legislativo)** do Diário Oficial do Estado do Rio de Janeiro para o gabinete da deputada estadual Dani Balbi.

Todo dia útil de manhã, um robô do GitHub faz quatro coisas:

1. baixa a edição do dia no site da Imprensa Oficial (IOERJ);
2. pede ao Claude um resumo do dia e a lista dos atos, marcando os que tratam de **LGBTQIA+**, **Mulheres** e **Ciência e Tecnologia**, além dos que envolvem o **gabinete**;
3. registra as nomeações, exonerações, designações e dispensas publicadas, por gabinete;
4. atualiza este painel, que a equipe abre pelo navegador.

Endereço do painel: `https://shamirarossi.github.io/Paineis-Gabinete-Dani-Balbi/radar-do-alerj/`

## Configuração (uma vez só)

1. **Chave da API do Claude.** Crie a chave em [console.anthropic.com](https://console.anthropic.com/), em *API Keys*. No repositório, cadastre-a em **Settings → Secrets and variables → Actions → New repository secret**, com o nome `ANTHROPIC_API_KEY`.
2. **Permissão para o robô gravar.** Em **Settings → Actions → General → Workflow permissions**, marque **Read and write permissions** e salve.
3. **Site ligado.** Em **Settings → Pages**, confira se está em **Deploy from a branch**, branch `main`, pasta `/ (root)`. É a mesma configuração do Radar ALESP.
4. **Teste.** Em **Actions → Radar DO ALERJ - leitura diária → Run workflow**, rode uma vez e confira o painel.

## Como funciona

| Quando | O que acontece |
| --- | --- |
| Dias úteis, 8h47 (horário de Brasília) | Primeira leitura do dia. |
| Dias úteis, 11h17 | Leitura de reserva, caso a edição tenha saído tarde. Se a edição já estiver no painel, não faz nada. |
| Feriado ou dia sem Parte II | Nenhuma edição nova; só atualiza a hora da última verificação. |
| Falha (site fora do ar, erro da API) | O aviso aparece no topo do painel e o GitHub manda e-mail para quem administra o repositório. |

Para ler uma data específica ou refazer uma leitura, use **Run workflow**, preencha a data (`AAAA-MM-DD`) e marque *forçar* se a edição já estiver no painel.

**Custo:** cada leitura usa o Claude Sonnet 5.5 e custa por volta de US$ 0,10 a 0,15, cerca de US$ 3 por mês. Para trocar o modelo, crie a variável `MODELO` em **Settings → Secrets and variables → Actions → Variables**.

**Visibilidade:** o repositório é público, então qualquer pessoa com o link vê o painel, inclusive as notas "Por que importa". O conteúdo de base também é público (é o Diário Oficial), mas escreva as orientações internas pensando nisso.

## Arquivos

- `scripts/ler_do.py` é o robô. Ele faz uma leitura só para todos os gabinetes cadastrados em `PERFIS` (hoje, Dani Balbi e [Vinicius Cozzolino](../radar-vinicius-cozzolino/)). Os critérios de cada tema também ficam ali.
- `../leituras/AAAA-MM-DD.json` guarda a leitura completa de cada dia; cada painel recebe só a sua parte.
- `index.html` é o painel.
- `data/edicoes/AAAA-MM-DD.json` guarda uma edição por dia.
- `data/indice.json`, `data/destaques.json` e `data/pessoal.json` são a lista de edições, os atos por tema e os atos de pessoal; o robô os refaz a cada leitura.
- O agendamento fica em `../.github/workflows/radar-do-alerj.yml`.

Os resumos são gerados automaticamente. Antes de citar, confira sempre o texto original pelo link "Abrir o Diário Oficial".
