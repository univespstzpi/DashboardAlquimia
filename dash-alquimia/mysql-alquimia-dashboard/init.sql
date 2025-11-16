CREATE DATABASE IF NOT EXISTS historico_vendas_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE historico_vendas_db;

-- historico_vendas_db.vendas_detalhe definição

CREATE TABLE `vendas_detalhe` (
  `id` int NOT NULL AUTO_INCREMENT,
  `data_hora_item` datetime NOT NULL COMMENT 'Data/Hora Item',
  `data_abertura_ped` date DEFAULT NULL COMMENT 'Data Ab. Ped.',
  `data_fechamento_ped` datetime DEFAULT NULL COMMENT 'Data Fec. Ped.',
  `quantidade_item` int NOT NULL COMMENT 'Qtd.',
  `valor_unitario_item` decimal(10,2) NOT NULL COMMENT 'Valor Un. Item',
  `valor_total_item` decimal(10,2) NOT NULL COMMENT 'Valor. Tot. Item',
  `valor_produto` decimal(10,2) DEFAULT NULL COMMENT 'Valor Prod',
  `nome_produto` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Nome Prod',
  `tipo_item` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Tipo de Item',
  `tipo_produto` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Tipo Prod',
  `categoria_produto` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Cat. Prod.',
  `codigo_pedido` int DEFAULT NULL COMMENT 'Cod. Ped.',
  `numero_mesa_comanda` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Núm. Mesa/Com.',
  `tipo_pedido` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Tipo Ped.',
  `status_pedido` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Stat. Ped.',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=162575 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;