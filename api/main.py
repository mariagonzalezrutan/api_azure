from fastapi import FastAPI, Header, HTTPException
from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication
from azure.devops.v7_0.work_item_tracking.models import Wiql, JsonPatchOperation
from pydantic import BaseModel
from typing import Optional, Dict, Any

app = FastAPI()

# Define el modelo para el payload recibido
class Message(BaseModel):
    text: str
    html: Optional[str]
    markdown: Optional[str]

class Definition(BaseModel):
    id: int
    name: str
    url: str
    type: str

class Resource(BaseModel):
    id: int
    buildNumber: str
    status: str
    result: str
    queueTime: str
    startTime: str
    finishTime: str
    url: str
    definition: Definition
    sourceBranch: str
    sourceVersion: str
    logs: Dict[str, Any]

class AzurePayload(BaseModel):
    subscriptionId: str
    notificationId: int
    id: str
    eventType: str
    publisherId: str
    message: Message
    resource: Resource
    createdDate: str

@app.post("/")
def ejecutar_script_azure(payload: AzurePayload, authorization: str = Header(...)):
    try:
        print(f"Authorization header recibido: {authorization}")
        if authorization.startswith("Bearer "):
            personal_access_token = authorization.split(" ")[1]  # Quita "Bearer"
        else:
            personal_access_token = authorization
       
        organization_url = 'https://dev.azure.com/CorporacionRutaN'
        
        # Autenticación y conexión
        credentials = BasicAuthentication('', personal_access_token)
        connection = Connection(base_url=organization_url, creds=credentials)

        core_client = connection.clients.get_core_client()
        wit_client = connection.clients.get_work_item_tracking_client()

        # Procesar información del payload
        print(f"Procesando evento: {payload.eventType}")
        print(f"Build ID: {payload.resource.id}, Status: {payload.resource.status}")

        if payload.resource.status == "completed" and payload.resource.result == "succeeded":
            print(f"El build {payload.resource.buildNumber} fue exitoso.")
        else:
            print(f"El build {payload.resource.buildNumber} no fue exitoso.")

        # Consulta proyectos en Azure DevOps
        projects = core_client.get_projects()
        for project in projects:
            if project.name == "CATI":
                print(f"Proyecto: {project.name}")

                query = Wiql(query=f"SELECT [System.Id], [System.Title], [System.State] FROM workitems WHERE [System.TeamProject] = '{project.name}'")
                work_items_query_result = wit_client.query_by_wiql(wiql=query)
                
                if not work_items_query_result.work_items:
                    print(f"No se encontraron work items para el proyecto: {project.name}")
                    continue
                
                work_item_ids = [item.id for item in work_items_query_result.work_items]
                
                if work_item_ids:
                    work_items = wit_client.get_work_items(ids=work_item_ids, expand='All')
                    
                    for wi in work_items:
                        cantidad = wi.fields.get('Custom.Cantidad')
                        meses = wi.fields.get('Custom.Meses')
                        valor_unitario = wi.fields.get('Custom.Valorunitario')

                        if cantidad is not None and meses is not None and valor_unitario is not None:
                            valor_total_estimado = cantidad * meses * valor_unitario
                            valor_total_formateado = valor_total_estimado
                            print(f"    Calculando Valor Total Estimado: {valor_total_formateado}")
                            try:
                                update_document = [
                                    JsonPatchOperation(
                                        op="add",
                                        path="/fields/Custom.ValorTotal",
                                        value=valor_total_formateado
                                    )
                                ]
                                wit_client.update_work_item(
                                    document=update_document,
                                    id=wi.id
                                )
                                print(f" Valor Total Estimado actualizado en el work item ID {wi.id}: {valor_total_formateado}")
                            except Exception as e:
                                print(f"    Error al actualizar el work item ID {wi.id}: {e}")
                        else:
                            print(f" No se encontraron suficientes datos para calcular el valor total estimado para el work item ID {wi.id}")

                        print("====================================")
                else:
                    print(f"No se encontraron work items para el proyecto: {project.name}")

                print("====================================")
        return {"message": "Evento procesado y script ejecutado correctamente"}
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
