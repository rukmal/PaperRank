from .citation.ncbi_citation import NCBICitation as Citation
from collections import OrderedDict
from redis.client import StrictPipeline


def worker(pipe: StrictPipeline, linkset: OrderedDict) -> StrictPipeline:
    """Worker function. Queues actions in the `StrictPipeline` object to add
    tuples to GRAPH, maps outbound citations in OUT, adds unseen IDs to EXPLORE
    and removes current ID from INSTANCE.
    
    Arguments:
        pipe {StrictPipeline} -- Pipeline object to be used for queueing.
        linkset {OrderedDict} -- Raw response from the NCBI API.
    
    Returns:
        StrictPipeline -- Modified `StrictPipeline` object with new actions
                          queued.
    """

    # Create citation object
    citation = Citation(query_raw=linkset)

    if citation.error:
        # Escape, return unmodified pipe if there is an error
        return pipe
    
    # Adding to 'SEEN'
    pipe.sadd('SEEN', citation.id)

    # Building inbound and outbound tuples
    out_tuples = ['("{0}","{1}")'.format(citation.id, i)
                  for i in citation.outbound]
    in_tuples = ['("{0}","{1}")'.format(i, citation.id)
                 for i in citation.inbound]

    if (len(out_tuples) + len(in_tuples)) > 0:
        # Check if inbound or outbound citations exist

        # Adding tuples to `GRAPH`
        pipe.sadd('GRAPH', *in_tuples, *out_tuples)

        # Save outbound citations to `OUT`
        pipe.hmset('OUT', {citation.id: citation.outbound})

        # Add all inbound and outbound IDs to EXPLORE
        pipe.sadd('EXPLORE',
                  *citation.inbound, *citation.outbound)
        # Store the difference of `EXPLORE`` and `SEEN` in `EXPLORE`
        pipe.sdiffstore('EXPLORE', 'EXPLORE', 'SEEN')
    else:
        # No inbound or outbound citations; add to `DANGLING`
        pipe.sadd('DANGLING', citation.id)
    
    # Remove current ID from 'INSTANCE'
    pipe.srem('INSTANCE', citation.id)

    # Return pipe object with new instructions
    return pipe
