from arango import ArangoClient


class Jalapeno:
    def __init__(self, netloc, username, password, db_name="jalapeno"):
        self.client = ArangoClient(hosts=netloc)
        self.db = self.client.db(db_name, username=username, password=password)

    def get_least_utilized_path(self, src_ip, dst_ip):
        query = """
        FOR v, e IN OUTBOUND SHORTEST_PATH 'LSNode/%s' TO 'LSNode/%s' LS_Topology
            OPTIONS {weightAttribute: 'PercentUtilOutbound'}
            FILTER e != null
            RETURN e
        """ % (src_ip, dst_ip)
        cursor = self.db.aql.execute(query)
        return [edge for edge in cursor]
