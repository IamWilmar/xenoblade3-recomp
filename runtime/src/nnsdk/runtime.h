#pragma once
// Servicios internos de libnnsdk.so compartidos entre módulos (os, libc…).

#include <string>

#include "nnsdk/host.h"

namespace nnsdk {

const NnsdkHost& host();

// Cada hilo nuevo del juego avisa al loader (pila alternativa para el crash handler).
void on_thread_start();
// Al acabar la función de un hilo del juego: los destructores que registró con __cxa_thread_atexit (libc.cpp).
void run_thread_atexit();

// Ruta en el sistema de un archivo del juego ("rom:/movie/a.webm" -> su sitio en la SD); vacía sin punto de montaje.
std::string fs_host_path(const char* path);

// Modo TV: con <datos>/modo_tv al abrir el juego, la consola dice estar en la base (oe: modo Console y rendimiento
// Boost) y el mando es un mando Pro en el hueco No1 (en la base el portátil no cuenta como mando). Se decide una vez
// por sesión: el panel lo cambia para el próximo arranque.
bool tv_mode();

// El historial de frames de la capa (nn::vi::ListFrameHistory / GetLatestFrameNumber, vi.cpp). frame_queued: el juego
// acaba de presentar (nvnQueuePresentTexture); frame_presented: una imagen ha salido de verdad hacia la pantalla.
void frame_queued();
void frame_presented();

}  // namespace nnsdk
