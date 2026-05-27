"""
Neo4j 知识图谱服务
"""
from typing import List, Dict, Any, Optional
from functools import lru_cache
from neo4j import AsyncGraphDatabase, Result
from datetime import datetime

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class GraphService:
    """Neo4j 知识图谱服务"""
    
    # 节点类型
    NODE_TYPES = ["Employee", "Task", "Project", "Goal"]
    
    # 关系类型
    RELATION_TYPES = [
        "WORKS_ON",      # 员工-任务
        "OWNS",          # 员工-项目
        "PARTICIPATES_IN",  # 员工-项目
        "BELONGS_TO",    # 任务-项目
        "SUBTASK_OF",    # 任务-任务
        "ACHIEVES",      # 项目-目标
        "RELATED_TO",    # 通用关联
    ]
    
    def __init__(self, driver: AsyncGraphDatabase):
        self.driver = driver
    
    async def execute_cypher(self, query: str, params: Dict = None) -> List[Dict]:
        """执行Cypher查询"""
        async with self.driver.session() as session:
            result = await session.run(query, params or {})
            return await result.data()
    
    # ==================== 节点操作 ====================
    
    async def create_employee(self, employee_id: int, name: str, 
                               department: str, **kwargs) -> Dict:
        """创建员工节点"""
        query = """
        MERGE (e:Employee {employee_id: $employee_id})
        SET e.name = $name,
            e.department = $department,
            e.updated_at = datetime()
        RETURN e
        """
        result = await self.execute_cypher(query, {
            "employee_id": employee_id,
            "name": name,
            "department": department,
        })
        return result[0]["e"] if result else None
    
    async def create_task_node(self, task_id: int, title: str,
                                status: str, **kwargs) -> Dict:
        """创建任务节点"""
        query = """
        MERGE (t:Task {task_id: $task_id})
        SET t.title = $title,
            t.status = $status,
            t.updated_at = datetime()
        RETURN t
        """
        result = await self.execute_cypher(query, {
            "task_id": task_id,
            "title": title,
            "status": status,
        })
        return result[0]["t"] if result else None
    
    async def create_project_node(self, project_id: int, name: str,
                                   status: str = "active", **kwargs) -> Dict:
        """创建项目节点"""
        query = """
        MERGE (p:Project {project_id: $project_id})
        SET p.name = $name,
            p.status = $status,
            p.updated_at = datetime()
        RETURN p
        """
        result = await self.execute_cypher(query, {
            "project_id": project_id,
            "name": name,
            "status": status,
        })
        return result[0]["p"] if result else None
    
    # ==================== 关系操作 ====================
    
    async def create_relationship(
        self,
        from_id: int,
        from_type: str,
        to_id: int,
        to_type: str,
        rel_type: str,
        properties: Dict = None,
    ) -> bool:
        """创建关系"""
        query = f"""
        MATCH (a:{from_type} {{{from_type.lower()}_id: $from_id}})
        MATCH (b:{to_type} {{{to_type.lower()}_id: $to_id}})
        MERGE (a)-[r:{rel_type}]->(b)
        SET r += $properties, r.updated_at = datetime()
        RETURN r
        """
        result = await self.execute_cypher(query, {
            "from_id": from_id,
            "to_id": to_id,
            "properties": properties or {},
        })
        return len(result) > 0
    
    # ==================== 查询操作 ====================
    
    async def find_employee_tasks(self, employee_id: int) -> List[Dict]:
        """查找员工参与的所有任务（多跳查询示例）"""
        query = """
        MATCH (e:Employee {employee_id: $employee_id})-[:WORKS_ON]->(t:Task)
        RETURN t
        ORDER BY t.updated_at DESC
        """
        result = await self.execute_cypher(query, {"employee_id": employee_id})
        return [r["t"] for r in result]
    
    async def find_employee_projects(self, employee_id: int) -> List[Dict]:
        """查找员工参与的项目"""
        query = """
        MATCH (e:Employee {employee_id: $employee_id})
              -[:OWNS|PARTICIPATES_IN]->(p:Project)
        RETURN p
        """
        result = await self.execute_cypher(query, {"employee_id": employee_id})
        return [r["p"] for r in result]
    
    async def find_employee_tasks_in_project(
        self,
        employee_id: int,
        project_id: int,
    ) -> List[Dict]:
        """查找员工在特定项目下的所有任务（核心多跳查询）"""
        query = """
        MATCH (e:Employee {employee_id: $employee_id})
              -[:WORKS_ON]->(t:Task)-[:BELONGS_TO]->
              (p:Project {project_id: $project_id})
        RETURN t, p
        ORDER BY t.updated_at DESC
        """
        result = await self.execute_cypher(query, {
            "employee_id": employee_id,
            "project_id": project_id,
        })
        return [{"task": r["t"], "project": r["p"]} for r in result]
    
    async def find_similar_employees(
        self,
        employee_id: int,
        depth: int = 2,
    ) -> List[Dict]:
        """查找相似员工（通过共同项目/任务）"""
        query = f"""
        MATCH (e1:Employee {{employee_id: $employee_id}})
        MATCH (e1)-[:WORKS_ON|PARTICIPATES_IN*1..{depth}]-(e2:Employee)
        WHERE e1 <> e2
        WITH e2, count(*) as commonality
        RETURN e2, commonality
        ORDER BY commonality DESC
        LIMIT 10
        """
        result = await self.execute_cypher(query, {"employee_id": employee_id})
        return [{"employee": r["e2"], "commonality": r["commonality"]} for r in result]
    
    async def get_entity_relationships(
        self,
        entity_id: int,
        entity_type: str,
        max_depth: int = 2,
    ) -> List[Dict]:
        """获取实体的所有关联关系"""
        query = f"""
        MATCH (e:{entity_type} {{{entity_type.lower()}_id: $entity_id}})
        MATCH (e)-[r]-(connected)
        RETURN e, r, connected
        LIMIT 100
        """
        result = await self.execute_cypher(query, {"entity_id": entity_id})
        return result
    
    async def get_graph_stats(self) -> Dict:
        """获取图谱统计信息"""
        query = """
        MATCH (n)
        WITH labels(n)[0] as type, count(*) as count
        RETURN type, count
        UNION ALL
        MATCH ()-[r]->()
        WITH type(r) as type, count(*) as count
        RETURN type, count
        """
        result = await self.execute_cypher(query)
        
        stats = {"nodes": {}, "relationships": {}}
        for r in result:
            if r.get("type"):
                if r["type"] in self.NODE_TYPES:
                    stats["nodes"][r["type"]] = r["count"]
                else:
                    stats["relationships"][r["type"]] = r["count"]
        
        return stats
    
    async def find_path(
        self,
        from_id: int,
        from_type: str,
        to_id: int,
        to_type: str,
    ) -> List[Dict]:
        """查找两个实体间的最短路径"""
        query = """
        MATCH path = shortestPath(
            (a:{from_type} {{{from_type.lower()}_id: $from_id}})-
            [*]-(b:{to_type} {{{to_type.lower()}_id: $to_id}})
        )
        RETURN path
        """.format(from_type=from_type, to_type=to_type)
        
        result = await self.execute_cypher(query, {
            "from_id": from_id,
            "to_id": to_id,
        })
        return result[0]["path"] if result else None


_graph_service_instance: Optional[GraphService] = None


@lru_cache()
def _get_graph_service_cached() -> GraphService:
    """同步缓存版本（供 async 函数调用）"""
    global _graph_service_instance
    if _graph_service_instance is None:
        from app.core.database import neo4j_driver
        _graph_service_instance = GraphService(neo4j_driver)
    return _graph_service_instance


async def get_graph_service() -> GraphService:
    """获取图谱服务实例"""
    return _get_graph_service_cached()
