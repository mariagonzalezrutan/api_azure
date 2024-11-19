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
def ejecutar_script_azure(payload: AzurePayload, authorization: str = Header(...)):
    try:
        # Extraer y procesar el token de autorización
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
        work_item_id = payload.resource.workItemId
        updated_fields = payload.resource.fields

        if updated_fields:
            print(f"Work item actualizado: {work_item_id}, Campos modificados:")
            for field, update in updated_fields.items():
                print(f"  Campo: {field}, Viejo valor: {update.oldValue}, Nuevo valor: {update.newValue}")
        else:
            print(f"No se detectaron campos actualizados en el work item ID {work_item_id}")

        # Obtener detalles del work item actualizado
        work_item = wit_client.get_work_item(id=work_item_id, expand='All')
        print(f"Detalles del work item: {work_item.fields}")

        # Procesar cualquier campo del work item actualizado
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
                wit_client.update_work_item(document=update_document, id=work_item_id)
                print(f"Valor Total Estimado actualizado en el work item ID {work_item_id}: {valor_total_estimado}")
            except Exception as e:
                print(f"Error al actualizar el work item ID {work_item_id}: {e}")
        else:
            print(f"No se encontraron suficientes datos para calcular el valor total estimado para el work item ID {work_item_id}")

        return {"message": "Evento procesado y script ejecutado correctamente"}
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))