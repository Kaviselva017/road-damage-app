import ast
import astor
import glob

files = glob.glob("backend/app/**/*.py", recursive=True)

class QueryTransformer(ast.NodeTransformer):
    def visit_Call(self, node):
        self.generic_visit(node)
        
        # Look for node.func == Attribute(attr='all'/'first'/'count')
        if not isinstance(node.func, ast.Attribute):
            return node
            
        attr_name = node.func.attr
        if attr_name not in ["all", "first"]:
            return node
            
        # The value must be a chain that goes down to db.query(...)
        # Let's see if the root of this chain is a Call to Attribute(attr='query', value=Name(id='db'))
        curr = node.func.value
        chain = []
        is_query = False
        while True:
            if isinstance(curr, ast.Call):
                if isinstance(curr.func, ast.Attribute):
                    if curr.func.attr == "query":
                        # Could be db.query
                        if isinstance(curr.func.value, ast.Name) and curr.func.value.id == "db":
                            is_query = True
                            query_args = curr.args
                            break
                curr = curr.func.value
            elif isinstance(curr, ast.Attribute):
                curr = curr.value
            else:
                break

        if not is_query:
            return node
            
        # We found a db.query(...).XYZ.all()
        # We want to replace db.query(Model).XYZ.all()
        # with db.execute(select(Model).XYZ).scalars().all()
        
        # Rebuild the XYZ part but rooted at select(Model)
        # However, AST manipulation like this requires replacing the root `curr` with select(Model)
        # But we don't have back-pointers in Python AST.
        pass

