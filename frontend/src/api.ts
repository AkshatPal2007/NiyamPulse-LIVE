export class ApiFailure extends Error {
  constructor(message:string, public status:number, public code?:string) {super(message)}
}

export async function requestApi<T>(path:string, csrf?:string, options:RequestInit={}):Promise<T> {
  const response=await fetch('/api/v2'+path,{...options,credentials:'include',headers:{
    ...(options.body?{'Content-Type':'application/json'}:{}),
    ...(csrf&&options.method&&options.method!=='GET'?{'X-CSRF-Token':csrf}:{}),...options.headers,
  }})
  if(!response.ok) {
    const error=await response.json().catch(()=>null)
    throw new ApiFailure(error?.message??'The request could not be completed. Please try again.',response.status,error?.code)
  }
  return response.status===204?undefined as T:response.json()
}
