// Configuração global do Chart.js
Chart.defaults.font.family = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif";
Chart.defaults.color = '#666';

// Função para formatar números como moeda brasileira
function formatCurrency(value) {
    return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL'
    }).format(value);
}

// Função para criar o gráfico de TOP 10 produtos
async function createTopProdutosChart() {
    try {
        const response = await fetch('/api/relatorios/top-10-produtos');
        const data = await response.json();

        const ctx = document.getElementById('topProdutosChart').getContext('2d');

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(item => item.produto),
                datasets: [{
                    label: 'Quantidade Pedida',
                    data: data.map(item => item.quantidade),
                    backgroundColor: '#667eea',
                    borderRadius: 8,
                }]
            },
            options: {
                indexAxis: 'y', // Transforma em gráfico de barras horizontais
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        grid: {
                            color: '#f0f0f0'
                        }
                    },
                    y: {
                        grid: {
                            display: false
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Erro ao criar gráfico de Top 10 Produtos:', error);
    }
}

// Função para criar o gráfico de faturamento mensal
async function createFaturamentoMensalChart() {
    try {
        const response = await fetch('/api/relatorios/faturamento-mensal');
        const data = await response.json();

        const ctx = document.getElementById('faturamentoMensalChart').getContext('2d');

        new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(item => item.mes),
                datasets: [{
                    label: 'Faturamento Mensal',
                    data: data.map(item => item.faturamento),
                    borderColor: '#764ba2',
                    backgroundColor: 'rgba(118, 75, 162, 0.1)',
                    fill: true,
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return 'Faturamento: ' + formatCurrency(context.parsed.y);
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: '#f0f0f0'
                        },
                        ticks: {
                            callback: function(value) {
                                return formatCurrency(value);
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
        console.error('Erro ao criar gráfico de Faturamento Mensal:', error);
    }
}

// Inicialização quando a página carrega
document.addEventListener('DOMContentLoaded', () => {
    createTopProdutosChart();
    createFaturamentoMensalChart();
});