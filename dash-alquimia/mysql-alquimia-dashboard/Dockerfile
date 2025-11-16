FROM mysql:latest

ENV MYSQL_ROOT_PASSWORD=admin@2025#

# Copia o script SQL para o diretório de inicialização do container.
# O Docker Engine do MySQL irá executar este script na primeira vez que for iniciado.
COPY init.sql /docker-entrypoint-initdb.d/

# Expõe a porta padrão do MySQL.
EXPOSE 3306

# O comando padrão para iniciar o servidor MySQL será executado.
CMD ["mysqld"]