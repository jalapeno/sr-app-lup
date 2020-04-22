from arango import ArangoClient


class Jalapeno:
    def __init__(self, netloc, username, password, db_name="jalapeno"):
        self.client = ArangoClient(hosts=netloc)
        self.db = self.client.db(db_name, username=username, password=password)

    def get_shortest_path(src_ip, dst_ip):
        query = """
        FOR v IN OUTBOUND 
        SHORTEST_PATH 'LSNode/{src_ip}' TO 'LSNode/{dst_ip}' LS_Topology
            RETURN v
        )
        """.format(
            src_ip=src_ip, dst_ip=dst_ip
        )
        cursor = db.aql.execute(query)
        return [name for name in cursor]
