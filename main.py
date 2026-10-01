import config
import neon_db
from ui.app import App


def main():
    app = App()  # se crea la ventana antes de tocar la red: si no hay internet o la conexión
    # no está configurada, la app igual abre y lo avisa, en vez de no arrancar.
    if config.obtener_connection_string():
        try:
            neon_db.init_db()  # crea la tabla si no existe — idempotente
        except neon_db.NeonError:
            pass  # la app queda usable igual, avisando en cada intento
    app.mainloop()


if __name__ == "__main__":
    main()