# Instalar en un servidor

1. Crear un servidor Ubuntu 24.04 (4 vCPU, 8 GB RAM) con los puertos 22, 80 y 443 abiertos.
2. (Opcional) Crear un registro DNS tipo A de tu dominio apuntando a la IP del servidor.
3. Bajar el código en el servidor:
       ssh root@IP_DEL_SERVIDOR
       git clone https://github.com/USUARIO/REPOSITORIO.git control-placas && cd control-placas
4. Instalar:  bash despliegue/instalar.sh
5. Abrir la dirección que muestra al final y entrar con el usuario y la contraseña.

Cambiar la cámara después: editar CAMARA_URL en el archivo .env y correr
    docker compose up -d camara
Ver lo que lee la cámara:  docker compose logs -f camara
Actualizar el código:      git pull && docker compose up -d --build
