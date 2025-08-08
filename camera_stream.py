#!/usr/bin/env python3
"""
Service de streaming de caméras RTSP/IP
Gère la capture et la diffusion des flux vidéo des caméras
"""

import cv2
import logging
import threading
import time
from datetime import datetime
from io import BytesIO
import base64
from PIL import Image
import numpy as np
from flask import Response, jsonify

logger = logging.getLogger(__name__)

class CameraStream:
    """Classe pour gérer un flux de caméra individuel"""
    
    def __init__(self, camera_id, rtsp_url, resolution=(640, 480), fps=15):
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self.resolution = resolution
        self.fps = fps
        self.capture = None
        self.is_active = False
        self.last_frame = None
        self.last_frame_time = None
        self.thread = None
        self.error_count = 0
        self.max_errors = 10
        
    def start_stream(self):
        """Démarre le flux de capture vidéo"""
        if self.is_active:
            return True
            
        try:
            self.capture = cv2.VideoCapture(self.rtsp_url)
            if not self.capture.isOpened():
                logger.error(f"Impossible d'ouvrir le flux RTSP pour la caméra {self.camera_id}: {self.rtsp_url}")
                return False
            
            # Configuration de la capture
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            self.capture.set(cv2.CAP_PROP_FPS, self.fps)
            self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Réduire la latence
            
            self.is_active = True
            self.error_count = 0
            
            # Démarrer le thread de capture
            self.thread = threading.Thread(target=self._capture_frames, daemon=True)
            self.thread.start()
            
            logger.info(f"Flux démarré pour la caméra {self.camera_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors du démarrage du flux caméra {self.camera_id}: {e}")
            return False
    
    def stop_stream(self):
        """Arrête le flux de capture vidéo"""
        self.is_active = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5.0)
        
        if self.capture:
            self.capture.release()
            self.capture = None
        
        logger.info(f"Flux arrêté pour la caméra {self.camera_id}")
    
    def _capture_frames(self):
        """Thread de capture des images (privé)"""
        frame_interval = 1.0 / self.fps
        
        while self.is_active and self.capture:
            try:
                ret, frame = self.capture.read()
                
                if not ret:
                    self.error_count += 1
                    if self.error_count >= self.max_errors:
                        logger.error(f"Trop d'erreurs de capture pour la caméra {self.camera_id}, arrêt du flux")
                        self.is_active = False
                        break
                    
                    time.sleep(0.1)
                    continue
                
                # Redimensionner l'image si nécessaire
                if frame.shape[:2] != (self.resolution[1], self.resolution[0]):
                    frame = cv2.resize(frame, self.resolution)
                
                self.last_frame = frame
                self.last_frame_time = datetime.now()
                self.error_count = 0
                
                time.sleep(frame_interval)
                
            except Exception as e:
                logger.error(f"Erreur de capture pour la caméra {self.camera_id}: {e}")
                self.error_count += 1
                time.sleep(1.0)
    
    def get_current_frame(self):
        """Récupère l'image actuelle"""
        return self.last_frame
    
    def get_frame_as_jpeg(self, quality=85):
        """Convertit l'image actuelle en JPEG"""
        if self.last_frame is None:
            return None
        
        try:
            # Encoder en JPEG
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
            result, encoded_img = cv2.imencode('.jpg', self.last_frame, encode_param)
            
            if result:
                return encoded_img.tobytes()
            
        except Exception as e:
            logger.error(f"Erreur d'encodage JPEG pour la caméra {self.camera_id}: {e}")
        
        return None
    
    def get_frame_as_base64(self, quality=85):
        """Convertit l'image actuelle en base64 pour affichage web"""
        jpeg_data = self.get_frame_as_jpeg(quality)
        if jpeg_data:
            return base64.b64encode(jpeg_data).decode('utf-8')
        return None
    
    def is_alive(self):
        """Vérifie si le flux est actif et récent"""
        if not self.is_active or self.last_frame_time is None:
            return False
        
        # Considérer comme mort si pas de nouvelle image depuis 30 secondes
        time_diff = (datetime.now() - self.last_frame_time).total_seconds()
        return time_diff < 30.0

class CameraStreamManager:
    """Gestionnaire global des flux de caméras"""
    
    def __init__(self):
        self.streams = {}
        self.lock = threading.Lock()
    
    def start_camera_stream(self, equipement):
        """Démarre le flux pour un équipement"""
        with self.lock:
            camera_id = equipement.id
            
            # Arrêter le flux existant si présent
            if camera_id in self.streams:
                self.streams[camera_id].stop_stream()
                del self.streams[camera_id]
            
            # Vérifier si l'équipement supporte le streaming
            if not equipement.has_stream_capability:
                logger.warning(f"Équipement {camera_id} ne supporte pas le streaming")
                return False
            
            # Créer et démarrer le nouveau flux
            resolution = equipement.get_stream_resolution()
            stream = CameraStream(
                camera_id=camera_id,
                rtsp_url=equipement.rtsp_stream_url,
                resolution=resolution,
                fps=equipement.fps or 15
            )
            
            if stream.start_stream():
                self.streams[camera_id] = stream
                logger.info(f"Flux démarré pour l'équipement {camera_id}")
                return True
            else:
                logger.error(f"Impossible de démarrer le flux pour l'équipement {camera_id}")
                return False
    
    def stop_camera_stream(self, camera_id):
        """Arrête le flux pour une caméra"""
        with self.lock:
            if camera_id in self.streams:
                self.streams[camera_id].stop_stream()
                del self.streams[camera_id]
                logger.info(f"Flux arrêté pour la caméra {camera_id}")
                return True
            return False
    
    def get_stream(self, camera_id):
        """Récupère un flux existant"""
        return self.streams.get(camera_id)
    
    def get_frame_stream(self, camera_id):
        """Générateur pour flux MJPEG"""
        stream = self.streams.get(camera_id)
        if not stream:
            return
        
        while stream.is_alive():
            jpeg_data = stream.get_frame_as_jpeg(quality=75)
            if jpeg_data:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg_data + b'\r\n')
            time.sleep(1.0 / (stream.fps or 15))
    
    def get_snapshot(self, camera_id):
        """Capture une image instantanée"""
        stream = self.streams.get(camera_id)
        if stream and stream.is_alive():
            return stream.get_frame_as_jpeg(quality=90)
        return None
    
    def cleanup_dead_streams(self):
        """Nettoie les flux morts"""
        with self.lock:
            dead_streams = []
            for camera_id, stream in self.streams.items():
                if not stream.is_alive():
                    dead_streams.append(camera_id)
            
            for camera_id in dead_streams:
                logger.info(f"Nettoyage du flux mort pour la caméra {camera_id}")
                self.streams[camera_id].stop_stream()
                del self.streams[camera_id]
    
    def get_streams_status(self):
        """Retourne le statut de tous les flux"""
        status = {}
        with self.lock:
            for camera_id, stream in self.streams.items():
                status[camera_id] = {
                    'active': stream.is_active,
                    'alive': stream.is_alive(),
                    'last_frame': stream.last_frame_time.isoformat() if stream.last_frame_time else None,
                    'error_count': stream.error_count,
                    'rtsp_url': stream.rtsp_url
                }
        return status
    
    def shutdown_all(self):
        """Arrête tous les flux"""
        with self.lock:
            for stream in self.streams.values():
                stream.stop_stream()
            self.streams.clear()
            logger.info("Tous les flux de caméras arrêtés")

# Instance globale du gestionnaire
camera_manager = CameraStreamManager()

# Arrêter tous les flux au démarrage pour éviter les conflits
camera_manager.shutdown_all()

def generate_stream_response(camera_id):
    """Génère une réponse HTTP pour le flux MJPEG"""
    return Response(
        camera_manager.get_frame_stream(camera_id),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )