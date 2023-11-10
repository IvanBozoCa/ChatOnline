import socket
import threading
import sys

# Parámetros del servidor a los que conectarse
SERVER_HOST = '127.0.0.1'  # Cambiar a la dirección del servidor si es necesario
SERVER_PORT = 5000
BUFFER_SIZE = 4096

# Crear un socket TCP/IP
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    # Conectar al servidor
    client_socket.connect((SERVER_HOST, SERVER_PORT))
except ConnectionRefusedError:
    print("No se pudo conectar al servidor.")
    sys.exit()

def receive_messages():
    while True:
        try:
            message = client_socket.recv(BUFFER_SIZE).decode('utf-8')
            print(message)  # Imprime cualquier mensaje recibido del servidor
            if "Nickname invalid or already taken." in message:
                client_socket.close()
                sys.exit()  # Salir del programa si el nickname es inválido o ya está tomado.
            if "[SERVER] Cuentame, ¿que artefactos tienes?" in message:
                # El servidor está pidiendo la lista de artefactos.
                artefactos = input("Ingresa tus artefactos separados por comas: ")
                client_socket.send(f"Artefactos: {artefactos}".encode('utf-8'))
        except Exception as e:
            print(f"Error al recibir datos: {e}")
            client_socket.close()
            break

def send_messages():
    while True:
        message = input('')
        if message == 'salir':
            client_socket.send(message.encode('utf-8'))  # Envía el comando de salida al servidor
            print("¡Adios y suerte completando tu coleccion!")
            client_socket.close()
            sys.exit()
        else:
            client_socket.send(message.encode('utf-8'))  # Envía el mensaje tal cual al servidor

nickname = input("Elija un nickname: ")
client_socket.send(nickname.encode('utf-8'))

# Crear y comenzar hilo para recibir mensajes
receive_thread = threading.Thread(target=receive_messages)
receive_thread.start()

# Crear y comenzar hilo para enviar mensajes
send_thread = threading.Thread(target=send_messages)
send_thread.start()

# Esperar a que los hilos terminen
receive_thread.join()
send_thread.join()
