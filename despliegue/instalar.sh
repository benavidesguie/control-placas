#!/usr/bin/env bash
# Instala el demo en un servidor Ubuntu 22.04/24.04 recién creado.
# Uso (como root o con sudo), dentro de la carpeta demo-placas:
#   bash despliegue/instalar.sh
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null; then
  echo "== Instalando Docker"
  curl -fsSL https://get.docker.com | sh
fi

echo
read -rp "Dominio para la página (ej. placas.miempresa.com). Deja vacío para usar la IP sin HTTPS: " DOMINIO
read -rp "Usuario para entrar a la página [admin]: " USUARIO
USUARIO=${USUARIO:-admin}
read -rsp "Contraseña para entrar a la página: " CLAVE; echo
[ -n "$CLAVE" ] || { echo "La contraseña no puede quedar vacía."; exit 1; }
read -rp "Dirección RTSP de la cámara (vacío = video de demostración en bucle): " CAMARA_URL

HASH=$(docker run --rm caddy:2 caddy hash-password --plaintext "$CLAVE")
SITIO=${DOMINIO:-":80"}
cat > despliegue/Caddyfile <<CADDY
$SITIO {
	encode gzip
	basic_auth {
		$USUARIO $HASH
	}
	reverse_proxy app:8501
}
CADDY

{
  echo "CAMARA_URL=${CAMARA_URL}"
  echo "CAMARA_NOMBRE=entrada"
  if [ -n "$CAMARA_URL" ]; then echo "REPETIR_VIDEO=0"; else echo "REPETIR_VIDEO=1"; fi
} > .env

echo "== Construyendo y arrancando (la primera vez tarda unos minutos)"
docker compose up -d --build

if [ -n "$DOMINIO" ]; then
  URL="https://$DOMINIO"
else
  URL="http://$(curl -fsS https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}')"
fi
echo
echo "Listo. Abre: $URL"
echo "Usuario: $USUARIO"
echo "Ver lo que hace la cámara: docker compose logs -f camara"
