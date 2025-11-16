// Configuração global do Chart.js
Chart.defaults.font.family = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif";
Chart.defaults.color = '#666';

// Variáveis globais para armazenar os gráficos
let producaoChart, receitaChart, despesasChart, margemChart;

// Função para formatar números como moeda brasileira
function formatCurrency(value) {
    return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL'
    }).format(value);
}

// Função para formatar números
function formatNumber(value, decimals = 0) {
    return new Intl.NumberFormat('pt-BR', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    }).format(value);
}

// Função para obter a string de consulta de data
function getDateQueryString() {
    const startDate = document.getElementById('start-date').value;
    const endDate = document.getElementById('end-date').value;

    if (startDate && endDate) {
        return `?start_date=${startDate}&end_date=${endDate}`;
    }
    return '';
}

// Função para carregar todos os dados do dashboard
async function updateAllData() {
    const query = getDateQueryString();

    try {
        // Carregar dados gerais e métricas em paralelo
        const [dadosGeraisRes, metricasRes] = await Promise.all([
            fetch(`/api/dashboard/dados-gerais${query}`),
            fetch(`/api/dashboard/metricas${query}`)
        ]);

        const dadosGerais = await dadosGeraisRes.json();
        const metricas = await metricasRes.json();

        document.getElementById('capacidade-total').textContent = formatNumber(dadosGerais.capacidade_total);
        document.getElementById('receita-potencial').textContent = formatCurrency(dadosGerais.receita_potencial_mes);
        document.getElementById('lucratividade').textContent = formatCurrency(dadosGerais.lucratividade_potencial_mes);
        document.getElementById('utilizacao-capacidade').textContent = formatNumber(metricas.utilizacao_capacidade_percent, 1);

        // Carregar os outros componentes
        const cervejasData = await fetchCervejasData(query);
        createProducaoChart(cervejasData);
        createReceitaChart(cervejasData);
        createMargemChart(cervejasData);
        loadCervejasTable(cervejasData);
        createDespesasChart(); // Despesas não são filtradas por data neste exemplo

    } catch (error) {
        console.error('Erro ao atualizar dados do dashboard:', error);
    }
}

// Função para buscar dados de cervejas
async function fetchCervejasData(query = '') {
    try {
        const response = await fetch(`/api/dashboard/cervejas${query}`);
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Erro ao buscar dados de cervejas:', error);
        return [];
    }
}

// Funções para criar/atualizar gráficos e tabelas
function createProducaoChart(data) {
    try {
        const ctx = document.getElementById('producaoChart').getContext('2d');
        
        if (producaoChart) {
            producaoChart.destroy();
        }
        
        producaoChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(cerveja => cerveja.nome),
                datasets: [{
                    label: 'Volume Produzido (L)',
                    data: data.map(cerveja => cerveja.volume_produzido),
                    backgroundColor: [
                        '#667eea',
                        '#764ba2',
                        '#f093fb',
                        '#f5576c',
                        '#4facfe',
                        '#00f2fe'
                    ],
                    borderRadius: 8,
                    borderSkipped: false,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: '#f0f0f0'
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Erro ao criar gráfico de produção:', error);
    }
}

function createReceitaChart(data) {
    try {
        const ctx = document.getElementById('receitaChart').getContext('2d');
        
        if (receitaChart) {
            receitaChart.destroy();
        }
        
        receitaChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.map(cerveja => cerveja.nome),
                datasets: [{
                    data: data.map(cerveja => cerveja.receita_total_potencial),
                    backgroundColor: [
                        '#667eea',
                        '#764ba2',
                        '#f093fb',
                        '#f5576c',
                        '#4facfe',
                        '#00f2fe'
                    ],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 20,
                            usePointStyle: true
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return context.label + ': ' + formatCurrency(context.parsed);
                            }
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Erro ao criar gráfico de receita:', error);
    }
}

// Gráfico de despesas (não depende do filtro de data neste exemplo)
async function createDespesasChart() {
    try {
        const response = await fetch('/api/dashboard/despesas');
        const data = await response.json();
        
        const despesas = data.principais_despesas_predio_mes;
        const labels = Object.keys(despesas).map(key => {
            return key.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
        });
        const values = Object.values(despesas);
        
        const ctx = document.getElementById('despesasChart').getContext('2d');
        
        if (despesasChart) {
            despesasChart.destroy();
        }
        
        despesasChart = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    backgroundColor: [
                        '#ff6b6b',
                        '#4ecdc4',
                        '#45b7d1',
                        '#96ceb4',
                        '#feca57',
                        '#ff9ff3'
                    ],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 15,
                            usePointStyle: true,
                            font: {
                                size: 11
                            }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return context.label + ': ' + formatCurrency(context.parsed);
                            }
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Erro ao criar gráfico de despesas:', error);
    }
}

function createMargemChart(data) {
    try {
        const ctx = document.getElementById('margemChart').getContext('2d');
        
        if (margemChart) {
            margemChart.destroy();
        }
        
        margemChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(cerveja => cerveja.nome),
                datasets: [{
                    label: 'Margem de Lucro (%)',
                    data: data.map(cerveja => cerveja.margem_lucro),
                    backgroundColor: data.map(cerveja => 
                        cerveja.margem_lucro > 50 ? '#4CAF50' : 
                        cerveja.margem_lucro > 30 ? '#FFC107' : '#F44336'
                    ),
                    borderRadius: 8,
                    borderSkipped: false,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        grid: {
                            color: '#f0f0f0'
                        },
                        ticks: {
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Erro ao criar gráfico de margem:', error);
    }
}

function loadCervejasTable(data) {
    try {
        const tbody = document.querySelector('#cervejas-table tbody');
        tbody.innerHTML = '';
        
        data.forEach(cerveja => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><strong>${cerveja.nome}</strong></td>
                <td>${formatNumber(cerveja.volume_produzido)}</td>
                <td>${formatNumber(cerveja.volume_real_produzido)}</td>
                <td>${formatCurrency(cerveja.custo_total_producao)}</td>
                <td>${formatCurrency(cerveja.receita_total_potencial)}</td>
                <td>${formatCurrency(cerveja.lucro_potencial)}</td>
                <td>${formatNumber(cerveja.margem_lucro, 1)}%</td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        console.error('Erro ao carregar a tabela de cervejas:', error);
    }
}

// Função para redimensionar gráficos
function resizeCharts() {
    if (producaoChart) producaoChart.resize();
    if (receitaChart) receitaChart.resize();
    if (despesasChart) despesasChart.resize();
    if (margemChart) margemChart.resize();
}

// Inicialização quando a página carrega
document.addEventListener('DOMContentLoaded', () => {
    // Define as datas padrão (últimos 30 dias)
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(endDate.getDate() - 30);

    document.getElementById('start-date').value = startDate.toISOString().split('T')[0];
    document.getElementById('end-date').value = endDate.toISOString().split('T')[0];

    // Carrega os dados iniciais
    updateAllData();

    // Adiciona o evento ao botão de filtro
    document.getElementById('filter-button').addEventListener('click', updateAllData);

    // Adiciona evento de redimensionamento
    window.addEventListener('resize', resizeCharts);
});

// Atualizar dados a cada 5 minutos
setInterval(() => {
    console.log("Atualizando dados automaticamente...");
    updateAllData();
}, 300000);
