import redis
import json

class RedisChatMemory:
    def __init__(self, host='localhost', port=6379, db=0, password=None):
        self.redis_client = redis.Redis(
            host=host, 
            port=port, 
            db=db, 
            password=password, 
            decode_responses=True
        )
        self.ttl = 86400  # 24 hour

    def _generate_key(self, tenant_id, employee_id, session_id):
        return f"chat_history:{tenant_id}:{employee_id}:{session_id}"

    def add_message(self, tenant_id, employee_id, session_id, role, content):
        key = self._generate_key(tenant_id, employee_id, session_id)
        message = json.dumps({"role": role, "content": content}, ensure_ascii=False)
        
        self.redis_client.rpush(key, message)

        self.redis_client.expire(key, self.ttl)

    def get_history(self, tenant_id, employee_id, session_id, limit=5):
        key = self._generate_key(tenant_id, employee_id, session_id)
        raw_history = self.redis_client.lrange(key, -limit, -1)
        
        return [json.loads(msg) for msg in raw_history]

    def clear_history(self, tenant_id, employee_id, session_id):
        key = self._generate_key(tenant_id, employee_id, session_id)
        self.redis_client.delete(key) 