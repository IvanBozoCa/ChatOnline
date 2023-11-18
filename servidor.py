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

# Crear un socket TCP/IP
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# Vincular el socket a la dirección y puerto
server_socket.bind((SERVER_HOST, SERVER_PORT))

# Escuchar conexiones entrantes
server_socket.listen(MAX_CONNECTIONS)

with open('artefactos.json', 'r') as file:
    artefactos = json.load(file)

print(f"Servidor escuchando en {SERVER_HOST}:{SERVER_PORT}...")

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
                elif message.startswith(":offer"):
                    _, recipient_nickname, my_artifact_id, their_artifact_id = message.split()
                    # Aquí debes añadir la lógica para manejar la oferta de intercambio de artefactos
                # Agregar aquí otros comandos
                elif message == ":smile":
                    client_socket.send(":)".encode('utf-8'))
                elif message == ':angry':
                    client_socket.send(">:(".encode('utf-8'))
                elif message == ':artefactos':
                    artefactos_usuario = clients[client_socket].get('artefactos', [])
                    artefactos_msg = "Tus artefactos son: " + ", ".join(artefactos_usuario)
                    client_socket.send(artefactos_msg.encode('utf-8'))
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
