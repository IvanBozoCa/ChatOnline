import socket
import threading
import json

# Parámetros del servidor
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
BUFFER_SIZE = 4096
MAX_CONNECTIONS = 3  # Máximo de clientes que pueden conectarse

# Lista de clientes conectados
clients = {}
pending_offers = {} 
# Crear un socket TCP/IP
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# Vincular el socket a la dirección y puerto
server_socket.bind((SERVER_HOST, SERVER_PORT))

# Escuchar conexiones entrantes
server_socket.listen(MAX_CONNECTIONS)
print(f"Servidor escuchando en {SERVER_HOST}:{SERVER_PORT}...")

with open('artefactos.json', 'r') as file:
    artefactos = json.load(file)
def send_message_to_client(nickname, message):
    # Encuentra el socket basado en el nickname y envía el mensaje.
    for sock, info in clients.items():
        if info['nickname'] == nickname:
            try:
                sock.send(message.encode('utf-8'))
                return
            except Exception as e:
                print(f"Error al enviar mensaje a {nickname}: {e}")
                return
    print(f"El usuario {nickname} no fue encontrado.")

def handle_offer(sender_nickname, recipient_nickname, sender_artifact_id, recipient_artifact_id):
    # Convertir IDs de artefactos a strings, asumiendo que los IDs en `artefactos.json` son enteros
    sender_artifact_id = str(sender_artifact_id)
    recipient_artifact_id = str(recipient_artifact_id)

    # Verificar que tanto el emisor como el receptor existan en la lista de clientes
    if recipient_nickname not in [info['nickname'] for _, info in clients.items()]:
        send_message_to_client(sender_nickname, "El usuario no existe o no está conectado.")
        return
    
    if sender_nickname not in [info['nickname'] for _, info in clients.items()]:
        send_message_to_client(sender_nickname, "Algo salió mal. No estás registrado correctamente en el servidor.")
        return

    # Verificar que el emisor tenga el artefacto que ofrece y el receptor tenga el artefacto que se solicita
    sender_socket = next((sock for sock, info in clients.items() if info['nickname'] == sender_nickname), None)
    recipient_socket = next((sock for sock, info in clients.items() if info['nickname'] == recipient_nickname), None)

    # Asegurarse de que ambos clientes están conectados
    if not sender_socket or not recipient_socket:
        send_message_to_client(sender_nickname, "Uno de los usuarios no está conectado.")
        return

    # Verificar posesión de artefactos
    if sender_artifact_id not in artefactos or recipient_artifact_id not in artefactos:
        send_message_to_client(sender_nickname, "Uno de los IDs de artefacto es inválido.")
        return

    if artefactos[sender_artifact_id] not in clients[sender_socket]['artefactos']:
        send_message_to_client(sender_nickname, "No posees ese artefacto.")
        return

    if artefactos[recipient_artifact_id] not in clients[recipient_socket]['artefactos']:
        send_message_to_client(sender_nickname, "El usuario no tiene el artefacto que deseas.")
        return

    # Si las verificaciones son exitosas, registrar la oferta
    pending_offers[recipient_nickname] = {
        'sender_nickname': sender_nickname,
        'sender_artifact_id': sender_artifact_id,
        'recipient_artifact_id': recipient_artifact_id
    }

    # Notificar al destinatario de la oferta
    send_message_to_client(recipient_nickname, f"Tienes una oferta de {sender_nickname}: {artefactos[sender_artifact_id]} por tu {artefactos[recipient_artifact_id]}")

def handle_accept(client_socket, recipient_nickname):
    # Verificar si hay una oferta pendiente para el usuario que quiere aceptar
    if recipient_nickname in pending_offers:
        offer = pending_offers[recipient_nickname]
        sender_nickname = offer['sender_nickname']
        sender_socket = None
        for sock, info in clients.items():
            if info['nickname'] == sender_nickname:
                sender_socket = sock
                break
        
        # Asegúrate de que tanto el emisor como el receptor todavía están conectados
        if not sender_socket or not client_socket:
            send_message_to_client(recipient_nickname, "El intercambio no puede realizarse porque uno de los usuarios no está conectado.")
            return
        
        # Asegúrate de que los artefactos aún existan
        if offer['sender_artifact_id'] not in clients[sender_socket]['artefactos'] or offer['recipient_artifact_id'] not in clients[client_socket]['artefactos']:
            send_message_to_client(recipient_nickname, "El intercambio no puede realizarse porque uno de los artefactos no está disponible.")
            return
        
        # Intercambiar los artefactos
        clients[sender_socket]['artefactos'].remove(offer['sender_artifact_id'])
        clients[sender_socket]['artefactos'].append(offer['recipient_artifact_id'])
        clients[client_socket]['artefactos'].remove(offer['recipient_artifact_id'])
        clients[client_socket]['artefactos'].append(offer['sender_artifact_id'])

        # Notificar a ambos usuarios sobre el intercambio exitoso
        send_message_to_client(sender_nickname, f"Intercambio exitoso. Has recibido {offer['recipient_artifact_id']} de {recipient_nickname}.")
        send_message_to_client(recipient_nickname, f"Intercambio exitoso. Has recibido {offer['sender_artifact_id']} de {sender_nickname}.")

        # Eliminar la oferta de la lista de pendientes
        del pending_offers[recipient_nickname]

        # Notificar a otros clientes sobre el intercambio realizado
        broadcast(f"¡Intercambio realizado entre {sender_nickname} y {recipient_nickname}!", 'SERVER', None)
    else:
        send_message_to_client(recipient_nickname, "No tienes ofertas pendientes para aceptar.")


def handle_reject(client_socket, sender_nickname):
    # Verificar si hay una oferta pendiente para el usuario
    if sender_nickname in pending_offers:
        del pending_offers[sender_nickname]
        broadcast("Intercambio rechazado.", 'SERVER', None)
    else:
        send_message_to_client(sender_nickname, "No tienes ofertas pendientes para rechazar.")


def broadcast(message, sender_nickname, sender_socket):
    for client_socket, info in clients.items():
        if client_socket != sender_socket:  # No enviar el mensaje al cliente que lo envió
            try:
                # Enviar el mensaje con el nombre del emisor
                client_socket.send(f"{sender_nickname}: {message}".encode('utf-8'))
            except Exception as e:
                print(f"Error al enviar mensaje: {e}")
                client_socket.close()
                remove_client(client_socket)



def handle_client(client_socket):
    client_socket.send("¡Bienvenid@ al chat de Granjerxs!\n[SERVER] Cuéntame, ¿qué artefactos tienes?".encode('utf-8'))
    
    while True:
        # Recibir y procesar la respuesta de artefactos
        artefactos_msg = client_socket.recv(BUFFER_SIZE).decode('utf-8')
        artefactos_ids = artefactos_msg.split(', ')
        artefactos_nombres = [artefactos[id] for id in artefactos_ids if id in artefactos]

        # Confirmar artefactos al cliente
        confirmacion = f"[SERVER] Tus artefactos son: {', '.join(artefactos_nombres)}\n¿Está bien? (Si/No)\n"
        client_socket.send(confirmacion.encode('utf-8'))

        # Recibir y procesar la confirmación del cliente
        confirmacion_respuesta = client_socket.recv(BUFFER_SIZE).decode('utf-8')
        if confirmacion_respuesta.lower() == 'si':
            client_socket.send("[SERVER] ¡OK!\n".encode('utf-8'))
            clients[client_socket]['artefactos'] = artefactos_nombres  # Almacenar los artefactos
            break
        elif confirmacion_respuesta.lower() == 'no':
            client_socket.send("[SERVER] Por favor, ingresa nuevamente los números de tus artefactos:".encode('utf-8'))
        else:
            client_socket.send("[SERVER] Respuesta no reconocida, por favor responde con 'Si' o 'No'.".encode('utf-8'))

    # Continuar con el resto del manejo del cliente
    while True:
        try:
            message = client_socket.recv(BUFFER_SIZE).decode('utf-8')
            if message:
                sender_nickname = clients[client_socket]['nickname']
                # Procesar comandos especiales aquí
                if message == ":q":
                    remove_client(client_socket)
                    break  # Terminar este hilo
                elif message.startswith(":p"):
                    parts = message.split(' ', 2)
                    # Verifica si el mensaje tiene la cantidad de partes esperada
                    if len(parts) == 3:
                        _, recipient_nickname, private_msg = parts
                        send_private_message(private_msg, recipient_nickname, sender_nickname, client_socket)
                    else:
                        error_msg = "Error: El formato del mensaje privado es incorrecto. Usa :p <destinatario> <mensaje>."
                        client_socket.send(error_msg.encode('utf-8'))
                elif message == ":u":
                    list_users(client_socket)
                elif message == ":smile":
                    client_socket.send(":)".encode('utf-8'))
                elif message == ':angry':
                    client_socket.send(">:(".encode('utf-8'))
                elif message == ':artefactos':
                    artefactos_usuario = clients[client_socket].get('artefactos', [])
                    artefactos_msg = "Tus artefactos son: " + ", ".join(artefactos_usuario)
                    client_socket.send(artefactos_msg.encode('utf-8'))
                elif message ==":offer":
                    _, recipient_nickname, my_artifact_id, their_artifact_id = message.split()
                    handle_offer(sender_nickname, recipient_nickname, my_artifact_id, their_artifact_id)
                elif message == ":accept":
                    handle_accept(client_socket, sender_nickname)

                elif message == ":reject":
                    handle_reject(client_socket, sender_nickname)
                else:
                    # Procesar envío de mensajes normales
                    broadcast(message, sender_nickname, client_socket)

        except socket.error as e:
            if e.errno == 10054:
                remove_client(client_socket)
                break
            else:
                remove_client(client_socket)
                break
        except Exception as e:
            print(f"Error: {e}")
            remove_client(client_socket)
            break

def remove_client(client_socket):
    nickname = clients[client_socket]['nickname']
    del clients[client_socket]  # Elimina al cliente antes de enviar el mensaje de desconexión
    broadcast(f"Cliente {nickname} desconectado.", '[SERVER]', None)
    client_socket.close()
    print(f"[SERVER] Cliente {nickname} desconectado.")  # Imprimir el mensaje en el servidor


def send_private_message(private_msg, recipient_nickname, sender_nickname, sender_socket):
    recipient_socket = None
    for sock, info in clients.items():
        if info['nickname'] == recipient_nickname:
            recipient_socket = sock
            break
    if recipient_socket:
        try:
            recipient_socket.send(f"Privado de {sender_nickname}: {private_msg}".encode('utf-8'))
        except Exception as e:
            print(f"Error enviando mensaje privado: {e}")
    else:
        # Si el destinatario no se encuentra, enviar un mensaje de error al emisor
        sender_socket.send(f"Usuario {recipient_nickname} no encontrado.".encode('utf-8'))


def receive_clients(server_socket):
    while True:
        client_socket, client_address = server_socket.accept()
        client_socket.send("Elija un nickname:".encode('utf-8'))
        
        nickname = client_socket.recv(BUFFER_SIZE).decode('utf-8').strip()
        if not nickname:
            client_socket.send("No se recibió un nickname válido. Conexión cerrada.".encode('utf-8'))
            client_socket.close()
            continue
        
        if nickname in [data['nickname'] for _, data in clients.items()]:
            client_socket.send("Nickname invalid or already taken. Conexión cerrada.".encode('utf-8'))
            client_socket.close()
            continue
        
        clients[client_socket] = {'nickname': nickname, 'address': client_address}
        
        # Confirmación del nickname
        client_socket.send("Nickname OK.".encode('utf-8'))
        
        print(f"[SERVER] Cliente {nickname} conectado.")
        broadcast(f"Cliente {nickname} conectado.", 'SERVER', client_socket)
        
        # Iniciar un nuevo hilo para atender al cliente
        thread = threading.Thread(target=handle_client, args=(client_socket,))
        thread.start()
        
        
def list_users(requesting_socket):
    user_list = "\n".join([info['nickname'] for sock, info in clients.items() if sock != requesting_socket])
    try:
        requesting_socket.send(f"Usuarios conectados:\n{user_list}".encode('utf-8'))
    except Exception as e:
        print(f"Error enviando lista de usuarios: {e}")
# El código para iniciar la función que acepta clientes
receive_clients_thread = threading.Thread(target=receive_clients, args=(server_socket,))
receive_clients_thread.start()
receive_clients_thread.join()  # Esto bloqueará hasta que el hilo termine

# Cerrar el socket del servidor cuando todos los hilos hayan terminado
server_socket.close()
