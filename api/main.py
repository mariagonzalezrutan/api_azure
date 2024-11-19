from fastapi import FastAPI, Header, HTTPException
from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication
from azure.devops.v7_0.work_item_tracking.models import Wiql, JsonPatchOperation
from pydantic import BaseModel
from typing import Optional, Dict, Any

app = FastAPI()

# Modelo del Payload de Azure
class Message(BaseModel):
    text: str
    html: Optional[str]
    markdown: Optional[str]

class RevisedBy(BaseModel):
    id: str
    displayName: str
    uniqueName: Optional[str]

class FieldUpdate(BaseModel):
    oldValue: Optional[Any]
    newValue: Optional[Any]

class Resource(BaseModel):
    id: int
    workItemId: int
    rev: int
    revisedBy: RevisedBy
    fields: Optional[Dict[str, FieldUpdate]]
    url: Optional[str]

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
def ejecutar_script_azure(payload: Optional[AzurePayload] = None, authorization: str = Header(...)):
    try:
        # Procesar el token de autorización
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
        projects = core_client.get_projects()
        for project in projects:
            query = Wiql(query=f"SELECT [System.Id], [System.Title], [System.State] FROM workitems WHERE [System.TeamProject] = '{project.name}'")
            work_items_query_result = wit_client.query_by_wiql(wiql=query)
            
            if not work_items_query_result.work_items:
                print(f"No se encontraron Work Items para el proyecto: {project.name}")
                continue
            
            work_item_ids = [item.id for item in work_items_query_result.work_items]
            work_items = wit_client.get_work_items(ids=work_item_ids, expand='All')
            for work_item in work_items:
                procesar_work_item(wit_client, work_item)

        # Si hay un payload, procesar solo el Work Item especificado
        if payload:
            work_item_id = payload.resource.workItemId
            print(f"Procesando evento para el Work Item ID: {work_item_id}")

            # Obtener detalles del Work Item
            work_item = wit_client.get_work_item(id=work_item_id, expand='All')
            procesar_work_item(wit_client, work_item)
            
        else:
            # Procesar todos los proyectos si no hay un payload
            print("Iterando sobre todos los proyectos y Work Items")
            projects = core_client.get_projects()
            for project in projects:
                query = Wiql(query=f"SELECT [System.Id], [System.Title], [System.State] FROM workitems WHERE [System.TeamProject] = '{project.name}'")
                work_items_query_result = wit_client.query_by_wiql(wiql=query)
                
                if not work_items_query_result.work_items:
                    print(f"No se encontraron Work Items para el proyecto: {project.name}")
                    continue
                
                work_item_ids = [item.id for item in work_items_query_result.work_items]
                work_items = wit_client.get_work_items(ids=work_item_ids, expand='All')
                for work_item in work_items:
                    procesar_work_item(wit_client, work_item)

        return {"message": "Script ejecutado correctamente"}
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def procesar_work_item(wit_client, work_item):
    """
    Procesa un Work Item específico, calculando y actualizando el valor total estimado.
    """
    try:
        cantidad = work_item.fields.get('Custom.Cantidad')
        meses = work_item.fields.get('Custom.Meses')
        valor_unitario = work_item.fields.get('Custom.Valorunitario')

        if cantidad is not None and meses is not None and valor_unitario is not None:
            valor_total_estimado = cantidad * meses * valor_unitario
            print(f"Calculando Valor Total Estimado: {valor_total_estimado}")
            try:
                update_document = [
                    JsonPatchOperation(
                        op="add",
                        path="/fields/Custom.ValorTotal",
                        value=valor_total_estimado
                    )
                ]
                wit_client.update_work_item(document=update_document, id=work_item.id)
                print(f"Valor Total Estimado actualizado en el Work Item ID {work_item.id}: {valor_total_estimado}")
            except Exception as e:
                print(f"Error al actualizar el Work Item ID {work_item.id}: {e}")
        else:
            print(f"No se encontraron suficientes datos para calcular el valor total estimado para el Work Item ID {work_item.id}")

    except Exception as e:
        print(f"Error procesando el Work Item ID {work_item.id}: {e}")
