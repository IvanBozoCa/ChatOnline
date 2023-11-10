import json
import socket
import select
import threading
from threading import Lock

# Cargar el archivo JSON con los nombres de los artefactos.
with open('artefactos.json', 'r') as file:
    artefact_names = json.load(file)

SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
MAX_CLIENTS = 3
BUFFER_SIZE = 4096

# Lista para manejar sockets de clientes
client_sockets = []
nicknames = []
client_artefacts = {}
pending_offers = {}

# Lock (mutex) para proteger las operaciones sobre datos compartidos
data_lock = Lock()

# Crear un socket TCP/IP
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((SERVER_HOST, SERVER_PORT))
server_socket.listen(MAX_CLIENTS)
print(f"Escuchando en {SERVER_HOST}:{SERVER_PORT}...")

def broadcast(message, sender_socket=None):
    for client_socket in client_sockets:
        if client_socket != sender_socket:
            client_socket.send(message)

def send_private_message(nickname, message):
    if nickname in nicknames:
        idx = nicknames.index(nickname)
        client_sockets[idx].send(message.encode('utf-8'))

def remove_socket(client_socket):
    if client_socket in client_sockets:
        idx = client_sockets.index(client_socket)
        nickname = nicknames[idx]
        client_sockets.remove(client_socket)
        nicknames.remove(nickname)
        client_artefacts.pop(nickname, None)
        broadcast(f"[SERVER] Cliente {nickname} desconectado.\n".encode('utf-8'))
        print(f"[SERVER] Cliente {nickname} desconectado.")

def welcome_goodbye_message(client_socket, nickname, is_welcome=True):
    if is_welcome:
        client_socket.send("¡Bienvenid@ al chat de Granjerxs!\n".encode('utf-8'))
        client_socket.send("[SERVER] Cuentame, ¿que artefactos tienes?\n".encode('utf-8'))
        broadcast(f"[SERVER] Cliente {nickname} conectado.\n".encode('utf-8'), client_socket)
    else:
        client_socket.send("¡Adios y suerte completando tu coleccion!\n".encode('utf-8'))
        broadcast(f"[SERVER] Cliente {nickname} desconectado.\n".encode('utf-8'), client_socket)

def handle_offer(client_socket, offer_nickname, my_artefact_id, their_artefact_id, nickname):
    if offer_nickname not in nicknames:
        client_socket.send(f"[SERVER] No hay ningun cliente con el nombre {offer_nickname}.\n".encode('utf-8'))
        return

    if my_artefact_id not in client_artefacts[nickname]:
        client_socket.send("[SERVER] No posees ese artefacto para ofrecer.\n".encode('utf-8'))
        return

    if their_artefact_id not in client_artefacts[offer_nickname]:
        client_socket.send("[SERVER] El otro cliente no posee el artefacto que pides.\n".encode('utf-8'))
        return

    # Si todo está en orden, añadir la oferta al registro de ofertas pendientes
    pending_offers[nickname] = (offer_nickname, my_artefact_id, their_artefact_id)
    send_private_message(offer_nickname, f"[SERVER] Tienes una oferta de intercambio de {nickname}: {my_artefact_id} por tu artefacto {their_artefact_id}.\n")

def handle_accept(client_socket, nickname):
    if nickname not in pending_offers:
        client_socket.send("[SERVER] No tienes ninguna oferta pendiente de aceptar.\n".encode('utf-8'))
        return

    offer_nickname, my_artefact_id, their_artefact_id = pending_offers[nickname]

    # Realizar el intercambio
    client_artefacts[nickname].remove(their_artefact_id)
    client_artefacts[nickname].append(my_artefact_id)
    client_artefacts[offer_nickname].remove(my_artefact_id)
    client_artefacts[offer_nickname].append(their_artefact_id)

    # Limpiar la oferta pendiente
    del pending_offers[nickname]

    # Informar a ambos clientes
    client_socket.send("[SERVER] ¡Intercambio realizado!\n".encode('utf-8'))
    send_private_message(offer_nickname, f"[SERVER] ¡Intercambio realizado con {nickname}!\n")


def handle_artefacts(client_socket, artefact_ids, nickname):
    artefact_list = [artefact_names[str(art_id)] for art_id in artefact_ids if str(art_id) in artefact_names]
    client_artefacts[nickname] = artefact_list
    client_socket.send(f"[SERVER] Tus artefactos son: {', '.join(artefact_list)}.\n¿Está bien? (Si/No)\n".encode('utf-8'))

def handle_commands(client_socket, message, nickname):
    parts = message.split(' ')
    command = parts[0]

    if command == ':q':
        remove_socket(client_socket)
    elif command == ':p' and len(parts) >= 3:
        target_nickname = parts[1]
        private_message = ' '.join(parts[2:])
        send_private_message(target_nickname, f"[PM de {nickname}]: {private_message}")
    elif command == ':u':
        online_users = ', '.join(nicknames)
        client_socket.send(f"[SERVER] Usuarios conectados: {online_users}\n".encode('utf-8'))
    elif command == ':smile':
        client_socket.send(":)\n".encode('utf-8'))
    elif command == ':angry':
        client_socket.send(">:(""\n".encode('utf-8'))
    elif command == ':offer' and len(parts) == 4:
        handle_offer(client_socket, parts[1], parts[2], parts[3], nickname)
    elif command == ':accept':
        handle_accept(client_socket, nickname)
    else:
        client_socket.send("[SERVER] Comando no reconocido.\n".encode('utf-8'))
        

def client_thread(client_socket, client_address):
    nickname = None  # Inicializar nickname como None
    try:
        # Solicitar y recibir el nickname del cliente
        client_socket.send("Por favor, envía tu nickname:".encode('utf-8'))
        nickname = client_socket.recv(BUFFER_SIZE).decode('utf-8').strip()
        
        # Comprobar y añadir el nickname a la lista de clientes
        with data_lock:
            if nickname in nicknames or not nickname:
                client_socket.send("Nickname invalid or already taken.\n".encode('utf-8'))
                client_socket.close()
                return
            else:
                client_sockets.append(client_socket)
                nicknames.append(nickname)
                client_artefacts[nickname] = []  # Inicializar lista de artefactos para el usuario

        # Informar en el servidor que un cliente se ha conectado
        print(f"[SERVER] Cliente {nickname} conectado desde {client_address}.")

        # Enviar bienvenida al cliente
        client_socket.send(f"¡Bienvenid@ al chat de Granjerxs, {nickname}!\n".encode('utf-8'))

        # Solicitar la lista de artefactos del cliente
        client_socket.send("[SERVER] Cuéntame, ¿qué artefactos tienes? (envía los IDs separados por comas)".encode('utf-8'))
        
        # Recibir la lista de artefactos del cliente
        artefactos_str = client_socket.recv(BUFFER_SIZE).decode('utf-8').strip()
        artefactos_ids = [int(id.strip()) for id in artefactos_str.split(',') if id.strip().isdigit()]

        # Añadir la lista de artefactos al cliente
        with data_lock:
            client_artefacts[nickname] = artefactos_ids

        # Enviar confirmación de artefactos al cliente
        artefactos_nombres = [artefact_names.get(str(id), "Artefacto desconocido") for id in artefactos_ids]
        client_socket.send(f"[SERVER] Tus artefactos son: {', '.join(artefactos_nombres)}.\n".encode('utf-8'))
        
        # Bucle para recibir y manejar comandos y mensajes del cliente
        while True:
            message = client_socket.recv(BUFFER_SIZE).decode('utf-8').strip()
            if message:
                with data_lock:
                    if message.startswith(':'):
                        handle_commands(client_socket, message, nickname)
                    else:
                        # Aquí se manejarían otros tipos de mensajes que no son comandos
                        pass
            else:
                # Cliente se desconectó
                break
    except ConnectionResetError:
        print(f"[SERVER] La conexión con el cliente {nickname} se cerró inesperadamente.")
    except ValueError as e:
        client_socket.send(f"[SERVER] Error: {e}\n".encode('utf-8'))
    except Exception as e:
        print(f"[SERVER] Error: {e}")
    finally:
        with data_lock:
            if nickname in nicknames:
                remove_socket(client_socket)
        client_socket.close()





while True:
    read_sockets, _, exception_sockets = select.select([server_socket] + client_sockets, [], client_sockets)

    for notified_socket in read_sockets:
        if notified_socket == server_socket:
            client_socket, client_address = server_socket.accept()
            nickname = client_socket.recv(BUFFER_SIZE).decode('utf-8').strip()
            threading.Thread(target=client_thread, args=(client_socket, client_address)).start()
            
            if nickname in nicknames or not nickname:
                client_socket.send("Nickname invalid or already taken.\n".encode('utf-8'))
                client_socket.close()
            else:
                client_sockets.append(client_socket)
                nicknames.append(nickname)
                print(f"[SERVER] Cliente {nickname} conectado.")
                welcome_goodbye_message(client_socket, nickname)
        else:
            try:
                message = notified_socket.recv(BUFFER_SIZE).decode('utf-8').strip()
                nickname = nicknames[client_sockets.index(notified_socket)]
                if message:
                    if message.lower() == 'no':
                        client_socket.send("[SERVER] ¡Vamos de nuevo! ¿Qué artefactos tienes?\n".encode('utf-8'))
                    elif message.lower() == 'si':
                        client_socket.send("[SERVER] ¡OK!\n".encode('utf-8'))
                    elif message.startswith(':'):
                        handle_commands(notified_socket, message, nickname)
                    else:
                        try:
                            # Asumimos que el mensaje es una lista de IDs de artefactos separados por comas.
                            artefact_ids = [int(id.strip()) for id in message.split(',')]
        
                            # Verificamos que el número de artefactos sea correcto
                            if 0 < len(artefact_ids):
                                handle_artefacts(notified_socket, artefact_ids, nickname)
                            else:
                                notified_socket.send("[SERVER] Error: Número de artefactos incorrecto, se esperaban de 1 a 6.\n".encode('utf-8'))

                        except ValueError:
                            # Si hay un ValueError, significa que el mensaje no era una lista de números.
                            notified_socket.send("[SERVER] Error: Se esperaba una lista de IDs de artefactos o algun comando\n".encode('utf-8'))

                else:
                    print(f"[SERVER] Cliente {nickname} se desconectó.")
                    remove_socket(notified_socket)
            except ConnectionResetError:
                # Esta excepción específica significa que la conexión fue cerrada inesperadamente
                print(f"[SERVER] La conexión con el cliente {nickname} se cerró inesperadamente.")
                remove_socket(notified_socket)
            except Exception as e:
                print(f"Error: {e}")
                remove_socket(notified_socket)

    for notified_socket in exception_sockets:
        remove_socket(notified_socket)

server_socket.close()
