import datetime
import logging
import sys

from daphne.endpoints import build_endpoint_description_strings
from daphne.server import Server
from django.apps import apps
from django.conf import settings
from django.core.management.commands.runserver import \
    Command as RunserverCommand
from django.utils.module_loading import import_string

from asgi_cable import __version__

# from ...staticfiles import StaticFilesWrapper

logger = logging.getLogger("django.channels.server")


def get_default_application():
    return import_string(settings.ASGI_APPLICATION)


class Command(RunserverCommand):
    protocol = "http"
    server_cls = Server

    def inner_run(self, *args, **options):
        self.stdout.write("Performing system checks...\n\n")
        self.check(display_num_errors=True)
        self.check_migrations()
        quit_command = "CTRL-BREAK" if sys.platform == "win32" else "CONTROL-C"
        now = datetime.datetime.now().strftime("%B %d, %Y - %X")
        self.stdout.write(now)
        self.stdout.write(
            (
                "Django version %(version)s, using settings %(settings)r\n"
                "Starting ASGI version %(channels_version)s development server"
                " at %(protocol)s://%(addr)s:%(port)s/\n"
                "Quit the server with %(quit_command)s.\n"
            )
            % {
                "version": self.get_version(),
                "channels_version": __version__,
                "settings": settings.SETTINGS_MODULE,
                "protocol": self.protocol,
                "addr": "[%s]" % self.addr if self._raw_ipv6 else self.addr,
                "port": self.port,
                "quit_command": quit_command,
            }
        )

        logger.debug("Daphne running, listening on %s:%s", self.addr,
                     self.port)

        endpoints = build_endpoint_description_strings(host=self.addr,
                                                       port=self.port)
        try:
            self.server_cls(
                application=self.get_application(options),
                endpoints=endpoints,
                signal_handlers=not options["use_reloader"],
                action_logger=self.log_action,
                root_path=getattr(settings, "FORCE_SCRIPT_NAME", "") or "",
            ).run()
            logger.debug("Daphne exited")
        except KeyboardInterrupt:
            shutdown_message = options.get("shutdown_message", "")
            if shutdown_message:
                self.stdout.write(shutdown_message)
            return

    def get_application(self, options):
        """
        Returns the static files serving application wrapping the default application,
        if static files should be served. Otherwise just returns the default
        handler.
        """
        staticfiles_installed = apps.is_installed("django.contrib.staticfiles")
        use_static_handler = options.get("use_static_handler",
                                         staticfiles_installed)
        insecure_serving = options.get("insecure_serving", False)
        # if use_static_handler and (settings.DEBUG or insecure_serving):
        #     return StaticFilesWrapper(get_default_application())
        # else:
        return get_default_application()

    def log_action(self, protocol, action, details):
        """
        Logs various different kinds of requests to the console.
        """
        # HTTP requests
        if protocol == "http" and action == "complete":
            msg = "HTTP %(method)s %(path)s %(status)s [%(time_taken).2f, %(client)s]"

            # Utilize terminal colors, if available
            if 200 <= details["status"] < 300:
                # Put 2XX first, since it should be the common case
                logger.info(self.style.HTTP_SUCCESS(msg), details)
            elif 100 <= details["status"] < 200:
                logger.info(self.style.HTTP_INFO(msg), details)
            elif details["status"] == 304:
                logger.info(self.style.HTTP_NOT_MODIFIED(msg), details)
            elif 300 <= details["status"] < 400:
                logger.info(self.style.HTTP_REDIRECT(msg), details)
            elif details["status"] == 404:
                logger.warn(self.style.HTTP_NOT_FOUND(msg), details)
            elif 400 <= details["status"] < 500:
                logger.warn(self.style.HTTP_BAD_REQUEST(msg), details)
            else:
                # Any 5XX, or any other response
                logger.error(self.style.HTTP_SERVER_ERROR(msg), details)

        # Websocket requests
        elif protocol == "websocket" and action == "connected":
            logger.info("WebSocket CONNECT %(path)s [%(client)s]", details)
        elif protocol == "websocket" and action == "disconnected":
            logger.info("WebSocket DISCONNECT %(path)s [%(client)s]", details)
        elif protocol == "websocket" and action == "connecting":
            logger.info("WebSocket HANDSHAKING %(path)s [%(client)s]", details)
        elif protocol == "websocket" and action == "rejected":
            logger.info("WebSocket REJECT %(path)s [%(client)s]", details)
