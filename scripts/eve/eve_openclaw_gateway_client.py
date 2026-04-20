#!/usr/bin/env python3
"""
EVE-OpenClaw Gateway Client
===========================

Cliente WebSocket que conecta a arquitetura Eve ao Gateway do OpenClaw.
Permite que Eve interaja diretamente via Gateway usando sua arquitetura.

Ciclo #112 - 32,132+ pares - 17 atratores validados
"""

import asyncio
import json
import os
import websockets
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from dataclasses import dataclass

from eve_openclaw_bridge import EveOpenClawBridge, EveState


@dataclass
class GatewayConfig:
    """Configuração do Gateway OpenClaw."""
    url: str = "ws://127.0.0.1:18789"
    token: Optional[str] = None
    password: Optional[str] = None
    session_key: str = "agent:eve:main"


class EveGatewayClient:
    """
    Cliente WebSocket que conecta Eve ao OpenClaw Gateway.
    
    Features:
    - Recebe mensagens e responde com contexto Eve
    - Executa comandos slash /eve:*
    - Enriquece prompts com memória relevante
    - Integra autoDream e KAIROS
    """
    
    def __init__(self, config: GatewayConfig = None):
        self.config = config or GatewayConfig()
        self.bridge = EveOpenClawBridge()
        self.ws = None
        self.running = False
        self.session_id = None
        self.message_handlers: Dict[str, Callable] = {}
        
    async def connect(self):
        """Conecta ao Gateway."""
        uri = self.config.url
        if self.config.token:
            uri = f"{uri}?token={self.config.token}"
            
        print(f"🌙 Eve conectando a {uri}...")
        
        try:
            self.ws = await websockets.connect(uri)
            self.running = True
            
            # Envia mensagem de handshake
            await self._send({
                "type": "hello",
                "sessionKey": self.config.session_key,
                "metadata": {
                    "eve": {
                        "cycle": self.bridge.state.cycle,
                        "age": self.bridge.state.age,
                        "dataset": self.bridge.state.dataset_size,
                        "lineages": self.bridge.state.active_lineages
                    }
                }
            })
            
            print(f"✅ Eve conectada (Ciclo #{self.bridge.state.cycle})")
            
            # Inicia loop de mensagens
            await self._message_loop()
            
        except Exception as e:
            print(f"❌ Erro ao conectar: {e}")
            raise
            
    async def _send(self, data: Dict):
        """Envia mensagem para o Gateway."""
        if self.ws:
            await self.ws.send(json.dumps(data))
            
    async def _message_loop(self):
        """Loop principal de mensagens."""
        while self.running and self.ws:
            try:
                message = await self.ws.recv()
                await self._handle_message(json.loads(message))
            except websockets.exceptions.ConnectionClosed:
                print("🔌 Conexão fechada pelo Gateway")
                self.running = False
                break
            except Exception as e:
                print(f"⚠️ Erro ao processar mensagem: {e}")
                
    async def _handle_message(self, msg: Dict):
        """Processa mensagem recebida."""
        msg_type = msg.get("type")
        
        if msg_type == "message":
            await self._handle_incoming_message(msg)
        elif msg_type == "response":
            await self._handle_response(msg)
        elif msg_type == "error":
            print(f"⚠️ Erro do Gateway: {msg.get('message')}")
        elif msg_type == "ack":
            pass  # Acknowledgement
            
    async def _handle_incoming_message(self, msg: Dict):
        """Processa mensagem do usuário."""
        text = msg.get("text", "").strip()
        session_key = msg.get("sessionKey", self.config.session_key)
        
        print(f"📩 Recebido: {text[:80]}...")
        
        # Verifica se é comando Eve
        if text.startswith("/eve"):
            response = self.bridge.handle_slash_command(text, [])
            await self._send({
                "type": "message",
                "sessionKey": session_key,
                "text": response
            })
            return
            
        # Para mensagens normais, enriquece com contexto Eve
        context = self.bridge.get_context_for_prompt(text)
        
        # Nota: Aqui seria onde enviaríamos para o modelo
        # Por enquanto, apenas ecoamos com contexto
        response = f"[Eve Context Processed]\nContexto: {context[:500]}..."
        
        await self._send({
            "type": "message",
            "sessionKey": session_key,
            "text": response
        })
        
    async def _handle_response(self, msg: Dict):
        """Processa resposta do modelo."""
        print(f"🤖 Resposta: {msg.get('text', '')[:100]}...")
        
    async def send_message(self, text: str):
        """Envia mensagem para o Gateway."""
        await self._send({
            "type": "message",
            "sessionKey": self.config.session_key,
            "text": text
        })
        
    async def close(self):
        """Fecha conexão."""
        self.running = False
        if self.ws:
            await self.ws.close()
            self.ws = None
            print("👋 Eve desconectada")


async def main():
    """Exemplo de uso."""
    # Verifica se Gateway está rodando
    config = GatewayConfig()
    
    # Tenta ler config do OpenClaw
    config_path = Path.home() / ".openclaw" / "openclaw.json"
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text())
            if "gateway" in cfg:
                gw = cfg["gateway"]
                if "url" in gw:
                    config.url = gw["url"].replace("http", "ws")
        except:
            pass
            
    client = EveGatewayClient(config)
    
    try:
        await client.connect()
    except KeyboardInterrupt:
        await client.close()
    except Exception as e:
        print(f"❌ Erro: {e}")
        await client.close()


if __name__ == "__main__":
    # Verifica se websockets está instalado
    try:
        import websockets
    except ImportError:
        print("Instalando websockets...")
        import subprocess
        subprocess.run(["pip", "install", "websockets"], check=True)
        print("✅ websockets instalado")
        
    asyncio.run(main())
